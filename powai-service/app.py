from datetime import date
from pathlib import Path
import calendar, base64, io
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_geom, reproject, Resampling
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window
from rasterio.io import MemoryFile
from pystac_client import Client
import planetary_computer
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image
from shapely.geometry import shape
from skimage.morphology import binary_opening, binary_dilation, binary_erosion, disk

app=FastAPI(title="Powai Change Analysis API")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
AREA=Path(__file__).parent/"study-area"/"outline_shape.shp"
CATALOG="https://planetarycomputer.microsoft.com/api/stac/v1"
SENTINEL_TILE="43QBB"
class AnalysisRequest(BaseModel):
    analysis:str="water"
    start_year:int=Field(default=2017,ge=2014,le=2026)
    end_year:int=Field(default=2026,ge=2014,le=2026)
    month:int=Field(default=3,ge=1,le=12)
    cloud:float=Field(default=30,ge=0,le=100)
    satellite:str="sentinel"
    builtup_threshold:float=Field(default=-0.32,ge=-1,le=1)

def find_scene(year,month,cloud,geom,satellite):
    if satellite=="sentinel" and (year<2015 or (year==2015 and month<6)):
        raise ValueError("Sentinel-2 cannot provide earlier imagery: Sentinel-2A launched on 23 June 2015 and its first image was acquired on 27 June 2015. The imagery archive begins in June 2015; choose June 2015 or later. A usable scene over Powai may begin later depending on the satellite orbit, coverage, and cloud conditions. Choose Landsat for earlier dates.")
    first=f"{year}-{month:02d}-01"; last=f"{year}-{month:02d}-{calendar.monthrange(year,month)[1]}"
    if satellite=="sentinel" and year==2015 and month==6: first="2015-06-27"
    collection="sentinel-2-l2a" if satellite=="sentinel" else "landsat-c2-l2"
    items=list(Client.open(CATALOG,modifier=planetary_computer.sign_inplace).search(collections=[collection],intersects=geom,datetime=f"{first}/{last}",query={"eo:cloud_cover":{"lt":cloud}},limit=100).items())
    if satellite=="sentinel":
        items=[item for item in items if item.id.find("_T"+SENTINEL_TILE+"_")>=0 or item.properties.get("s2:mgrs_tile")==SENTINEL_TILE]
        if not items: raise ValueError(f"Sentinel-2 tile {SENTINEL_TILE} data is unavailable for {year}-{month:02d} below {cloud}% cloud. Try another summer month or increase cloud limit.")
    if not items: raise ValueError(f"{satellite.title()} data is unavailable for {year}-{month:02d} below {cloud}% cloud cover. Try another summer month or increase cloud limit.")
    aoi=shape(geom); geo=gpd.GeoSeries([aoi],crs="EPSG:4326"); local_crs=geo.estimate_utm_crs(); aoi_projected=geo.to_crs(local_crs).iloc[0]; aoi_area=aoi_projected.area
    scored=[]
    for item in items:
        footprint=shape(item.geometry)
        projected=gpd.GeoSeries([footprint],crs="EPSG:4326").to_crs(local_crs).iloc[0]
        coverage=projected.intersection(aoi_projected).area/aoi_area if aoi_area else 0
        scored.append((coverage,float(item.properties.get("eo:cloud_cover",100)),item))
    valid=[x for x in scored if x[0]>=0.98]
    if not valid:
        best=max(scored,key=lambda x:x[0])[0]
        raise ValueError(f"No {satellite.title()} scene in {year}-{month:02d} covers the full Powai AOI. Best scene covers {best*100:.1f}%. Try another month or increase the cloud limit.")
    valid.sort(key=lambda x:x[1])
    return valid[0][2]
def analyze_scene(item,geom,kind,satellite,builtup_threshold=-0.32):
    if satellite=="landsat":
        names=["blue","green","red","nir08","swir16","swir22","qa_pixel"]
        arrays={}; transform=None; crs=None; projected_geom=None
        for name in names:
            with rasterio.open(item.assets[name].href) as src:
                if projected_geom is None: projected_geom=shape(transform_geom("EPSG:4326",src.crs,geom))
                window=from_bounds(*projected_geom.bounds,transform=src.transform).round_offsets().round_lengths()
                arrays[name]=src.read(1,window=window).astype("float32"); transform=src.window_transform(window); crs=src.crs
        inside=geometry_mask([projected_geom],out_shape=arrays[names[0]].shape,transform=transform,invert=True)
        bands={n:arrays[n]*0.0000275-0.2 for n in names[:-1]}
        qa=arrays["qa_pixel"].astype("uint16")
        clear=(arrays["qa_pixel"]>0)&((qa & ((1<<1)|(1<<2)|(1<<3)|(1<<4)|(1<<5)))==0)&inside
        resolution=30
    else:
        # Use the 20 m SWIR grid and resample 10 m visible/NIR and SCL onto it.
        target="B08" if kind=="water" else "B11"
        with rasterio.open(item.assets[target].href) as src:
            projected_geom=shape(transform_geom("EPSG:4326",src.crs,geom))
            window=from_bounds(*projected_geom.bounds,transform=src.transform).round_offsets().round_lengths()
            target=src.read(1,window=window).astype("float32")
            transform=src.window_transform(window); target_shape=target.shape; crs=src.crs
        inside=geometry_mask([projected_geom],out_shape=target_shape,transform=transform,invert=True)
        mapping={"blue":"B02","green":"B03","red":"B04","nir08":"B08","swir16":"B11","swir22":"B12","scl":"SCL"}
        arrays={}
        for key,assetname in mapping.items():
            with rasterio.open(item.assets[assetname].href) as src:
                window=from_bounds(*projected_geom.bounds,transform=src.transform).round_offsets().round_lengths()
                cut=src.read(1,window=window).astype("float32"); cut_transform=src.window_transform(window)
                out=np.zeros(target_shape,dtype="float32")
                reproject(cut,out,src_transform=cut_transform,src_crs=src.crs,dst_transform=transform,dst_crs=crs,resampling=Resampling.nearest)
                arrays[key]=out
        bands={n:arrays[n]*0.0001 for n in ["blue","green","red","nir08","swir16","swir22"]}
        scl=arrays["scl"].astype("uint8")
        clear=(scl>0)&~np.isin(scl,[1,3,8,9,10,11])&inside
        resolution=10 if kind=="water" else 20
    g=bands["green"]; sw=bands["swir16"]; eps=1e-8
    mndwi=(g-sw)/(g+sw+eps)
    ndwi=(g-bands["nir08"])/(g+bands["nir08"]+eps)
    water_candidate=((ndwi>0)|((arrays.get("scl",np.zeros_like(g))==6) if satellite=="sentinel" else False))&clear
    water=binary_opening(water_candidate,disk(1))
    raw={n:arrays[n] for n in ["blue","green","red","nir08","swir16","swir22"]}
    blue=bands["blue"]; sw2=bands["swir22"]; ratio=np.clip(bands["swir16"]/(sw2+eps),0,5)
    land=clear&~water
    # Match the project's ENDISI calibration using source DN-style band values.
    end_mndwi=(raw["green"]-raw["swir16"])/(raw["green"]+raw["swir16"]+eps)
    end_ratio=np.clip(raw["swir16"]/(raw["swir22"]+eps),0,5)
    end_blue=raw["blue"]
    alpha=(2*np.nanmean(end_blue[land]))/(np.nanmean(end_ratio[land])+np.nanmean(end_mndwi[land])**2+eps) if land.any() else 0
    term=alpha*(end_ratio+end_mndwi**2); endisi=(end_blue-term)/(end_blue+term+eps)
    built=(endisi>builtup_threshold)&clear&~water
    chosen=water if kind=="water" else built
    index=ndwi if kind=="water" else endisi
    area=float(chosen.sum()*resolution*resolution/1e6)
    rgb=np.stack([bands["red"],bands["green"],bands["blue"]],axis=-1)
    return area,chosen,clear,rgb,inside,index,resolution,transform,item.properties.get("datetime"),item.id,float(item.properties.get("eo:cloud_cover",0))
def png64(image):
    out=io.BytesIO(); Image.fromarray(image.astype("uint8")).save(out,format="PNG"); return "data:image/png;base64,"+base64.b64encode(out.getvalue()).decode()
def display_rgb(rgb,mask_arr=None,kind="water",inside=None):
    # Stable local stretch for a useful true-colour preview, with classified pixels tinted.
    lo=np.nanpercentile(rgb,2); hi=np.nanpercentile(rgb,98)
    norm=np.clip((rgb-lo)/(hi-lo+1e-8),0,1)
    out=(norm*255).astype("uint8")
    if inside is not None:
        # Tint the complete AOI so its extent remains obvious over the satellite image.
        tint=np.array([30,205,220],dtype="float32")
        out[inside]=(0.78*out[inside]+0.22*tint).astype("uint8")
    if mask_arr is not None:
        if kind=="water": out[mask_arr]=[27,151,193]
        else: out[mask_arr]=[221,105,61]
    out[~np.isfinite(rgb).all(axis=2)]=[0,0,0]
    if inside is not None:
        edge=binary_dilation(inside,disk(2)) & ~binary_erosion(inside,disk(2))
        out[edge]=[255,235,0]
    return out
def render_index(index,valid,inside):
    index=np.where(valid,index,0)
    v=np.clip((index+1)/2,0,1)
    img=np.stack([255*v,255*(1-np.abs(2*v-1)),255*(1-v)],axis=-1).astype("uint8")
    img[~valid]=[220,220,220]
    edge=binary_dilation(inside,disk(2))&~binary_erosion(inside,disk(2)); img[edge]=[255,235,0]
    return png64(img)
def render_binary(mask_arr,valid,inside,kind):
    img=np.zeros((*mask_arr.shape,3),dtype="uint8"); img[:]=[238,238,232]
    img[~valid]=[185,185,185]
    color=[24,145,210] if kind=="water" else [225,105,55]
    img[mask_arr]=color
    edge=binary_dilation(inside,disk(2))&~binary_erosion(inside,disk(2)); img[edge]=[255,235,0]
    return png64(img)
@app.get("/")
def home():
    page=Path(__file__).resolve().parent.parent/"index.html"
    if not page.exists(): raise HTTPException(404,"Website file index.html is missing")
    return FileResponse(page)
@app.get("/api/study-area")
def study_area():
    if not AREA.exists(): raise HTTPException(404,"Study boundary file is missing")
    return gpd.read_file(AREA).to_crs(4326).__geo_interface__
@app.get("/api/health")
def health(): return {"status":"ok","study_area":AREA.exists(),"collection":"landsat-c2-l2 / sentinel-2-l2a","change_area_schema":"target-change-areas-v1","change_area_fields":["unchanged","reduced","increased"],"custom_layer_schema":"single-band-geotiff-v1"}
@app.post("/api/analyze")
def analyze(req:AnalysisRequest):
    if req.start_year>=req.end_year: raise HTTPException(400,"End year must be later than start year")
    try:
        gdf=gpd.read_file(AREA)
        if gdf.crs is None: raise ValueError("Study boundary has no coordinate reference system")
        geom=gdf.to_crs(4326).geometry.union_all().__geo_interface__
        if req.satellite not in ("landsat","sentinel"): raise ValueError("Choose Landsat or Sentinel-2.")
        a=find_scene(req.start_year,req.month,req.cloud,geom,req.satellite); b=find_scene(req.end_year,req.month,req.cloud,geom,req.satellite)
        av,am,ac,ar,ai,ix_a,res_a,_,ad,aid,acl=analyze_scene(a,geom,req.analysis,req.satellite,req.builtup_threshold)
        bv,bm,bc,br,bi,ix_b,res_b,_,bd,bid,bcl=analyze_scene(b,geom,req.analysis,req.satellite,req.builtup_threshold)
        warnings=[]
        if av<=0: warnings.append(f"No {req.analysis} pixels classified in {req.start_year}; inspect preview and try another date or threshold.")
        if bv<=0: warnings.append(f"No {req.analysis} pixels classified in {req.end_year}; inspect preview and try another date or threshold.")
        change=bv-av
        valid_both=ac&bc&ai&bi
        change_codes=np.where(valid_both,am.astype("uint8")+10*bm.astype("uint8"),255).astype("uint8")
        change_image=np.full((*change_codes.shape,3),[220,220,220],dtype="uint8")
        change_image[change_codes==0]=[232,236,233]
        change_image[change_codes==1]=[235,74,86]
        change_image[change_codes==10]=[45,150,235]
        change_image[change_codes==11]=[45,185,115]
        binary_stats={"earlier_pct":round(float(am[ac].mean()*100),2) if ac.any() else 0.0,"later_pct":round(float(bm[bc].mean()*100),2) if bc.any() else 0.0}
        denominator=max(int(valid_both.sum()),1)
        change_stats={str(code):round(float(np.sum(change_codes[valid_both]==code)/denominator*100),2) for code in [0,1,10,11]}
        pixel_km2=(res_a*res_a)/1e6
        change_areas={"unchanged":round(float(np.sum(valid_both&(change_codes==11))*pixel_km2),4),"reduced":round(float(np.sum(valid_both&(change_codes==1))*pixel_km2),4),"increased":round(float(np.sum(valid_both&(change_codes==10))*pixel_km2),4)}
        legend=("0 non-target in both dates · 1 target loss · 10 target gain · 11 target unchanged · gray cloud/no-data" if req.analysis=="water" else "0 non-target in both dates · 1 target loss · 10 target gain · 11 target unchanged · gray cloud/no-data")
        return {"analysis":req.analysis,"metric":"water_area_km2" if req.analysis=="water" else "builtup_area_km2","earlier":{"year":req.start_year,"area_km2":round(av,4),"date":ad,"scene":aid,"cloud":acl},"later":{"year":req.end_year,"area_km2":round(bv,4),"date":bd,"scene":bid,"cloud":bcl},"change_km2":round(change,4),"change_percent":round(change/av*100,2) if av else None,"warnings":warnings,"change_legend":legend,"binary_stats":binary_stats,"change_stats":change_stats,"change_areas_km2":change_areas,"change_preview":png64(change_image),"previews":{"earlier":png64(display_rgb(ar,None,req.analysis,ai)),"later":png64(display_rgb(br,None,req.analysis,bi)),"index_earlier":render_index(ix_a,ac,ai),"index_later":render_index(ix_b,bc,bi),"binary_earlier":render_binary(am,ac,ai,req.analysis),"binary_later":render_binary(bm,bc,bi,req.analysis)},"method":("Sentinel-2 L2A tile 43QBB, 10 m for water/20 m built-up" if req.satellite=="sentinel" else "Landsat Collection 2 Level-2 30 m")+" surface reflectance; cloud/shadow/snow masked; NDWI > 0 for water; Sentinel SCL water class included; ENDISI > "+str(req.builtup_threshold)+" for built-up; pixels clipped to Powai boundary."}
    except Exception as e: raise HTTPException(502,str(e))

def _read_reference_grid(content,geom):
    with MemoryFile(content) as mem:
        with mem.open() as src:
            if src.count!=1: raise ValueError("Upload one single-band GeoTIFF per band prompt; multi-band stacks are not accepted here.")
            if src.crs is None or not src.crs.is_projected: raise ValueError("The earlier Green band must use a projected CRS in metres. Reproject the input bands to UTM Zone 43N (EPSG:32643) before uploading.")
            projected_geom=shape(transform_geom("EPSG:4326",src.crs,geom))
            window=from_bounds(*projected_geom.bounds,transform=src.transform).round_offsets().round_lengths()
            window=window.intersection(Window(0,0,src.width,src.height)).round_offsets().round_lengths()
            if window.width<1 or window.height<1: raise ValueError("The earlier Green band does not cover the Powai study area.")
            transform=src.window_transform(window); data=src.read(1,window=window).astype("float32")
            data[src.read_masks(1,window=window)==0]=np.nan
            factor=src.crs.axis_info[0].unit_conversion_factor or 1.0
            pixel_km2=abs(transform.a*transform.e-transform.b*transform.d)*(factor**2)/1e6
            return data,transform,src.crs,projected_geom,pixel_km2

def _warp_uploaded_band(content,out_shape,out_transform,out_crs):
    with MemoryFile(content) as mem:
        with mem.open() as src:
            if src.count!=1: raise ValueError("Upload one single-band GeoTIFF per band prompt; multi-band stacks are not accepted here.")
            if src.crs is None: raise ValueError("An uploaded band has no coordinate reference system. Export it with its CRS attached.")
            source=src.read(1).astype("float32")
            source[src.read_masks(1)==0]=np.nan
            destination=np.full(out_shape,np.nan,dtype="float32")
            reproject(source=source,destination=destination,src_transform=src.transform,src_crs=src.crs,src_nodata=np.nan,dst_transform=out_transform,dst_crs=out_crs,dst_nodata=np.nan,resampling=Resampling.bilinear)
            return destination

def _classify_uploaded(arrays,kind,threshold,inside):
    valid=inside.copy()
    for array in arrays.values(): valid &= np.isfinite(array)
    eps=1e-8; green=arrays["green"]
    if kind=="water":
        index=(green-arrays["nir"])/(green+arrays["nir"]+eps)
        chosen=binary_opening((index>0)&valid,disk(1))
        rgb=np.stack([arrays["nir"],green,green],axis=-1)
        preview_note="NIR/Green/Green false-colour preview; NDWI = (Green − NIR) / (Green + NIR); water where NDWI > 0."
    else:
        swir1=arrays["swir1"]; swir2=arrays["swir2"]; blue=arrays["blue"]
        water_index=(green-arrays["nir"])/(green+arrays["nir"]+eps)
        water=binary_opening((water_index>0)&valid,disk(1))
        land=valid&~water
        mndwi=(green-swir1)/(green+swir1+eps)
        ratio=np.clip(swir1/(swir2+eps),0,5)
        alpha=(2*np.nanmean(blue[land]))/(np.nanmean(ratio[land])+np.nanmean(mndwi[land]**2)+eps) if land.any() else 0.0
        term=alpha*(ratio+mndwi**2)
        index=(blue-term)/(blue+term+eps)
        chosen=(index>threshold)&valid&~water
        rgb=np.stack([arrays["red"],green,blue],axis=-1)
        preview_note=f"ENDISI built-up index > {threshold}; water excluded with NDWI > 0."
    area=float(chosen.sum())
    return area,chosen,valid,rgb,np.where(valid,index,np.nan),preview_note

@app.post("/api/analyze/upload")
async def analyze_uploaded(request:Request):
    try:
        form=await request.form(max_files=20,max_fields=30)
        kind=str(form.get("analysis","water")); satellite=str(form.get("satellite","sentinel"))
        if kind not in ("water","built"): raise ValueError("Choose Water changes or Built-up changes before uploading bands.")
        if satellite not in ("sentinel","landsat"): raise ValueError("Choose Sentinel-2 or Landsat for the band mapping.")
        start_year=int(form.get("start_year",2017)); end_year=int(form.get("end_year",2026)); threshold=float(form.get("builtup_threshold",-0.32))
        if start_year>=end_year: raise ValueError("The later year must be after the earlier year.")
        if not -1<=threshold<=1: raise ValueError("ENDISI threshold must be between -1 and 1.")
        roles=["green","nir"] if kind=="water" else ["blue","green","red","nir","swir1","swir2"]
        payloads={}; total=0
        for date_key in ("earlier","later"):
            for role in roles:
                name=f"{date_key}_{role}"; upload=form.get(name)
                if upload is None or not hasattr(upload,"read") or not upload.filename: raise ValueError(f"Select a GeoTIFF for {date_key} {role.upper()}.")
                data=await upload.read(); total+=len(data)
                if len(data)>25*1024*1024: raise ValueError(f"{name} is larger than 25 MB. Clip/export the band to the Powai study area and try again.")
                payloads[name]=data
        if total>120*1024*1024: raise ValueError("The upload set is larger than 120 MB. Clip every band to the Powai study area before uploading.")
        gdf=gpd.read_file(AREA)
        if gdf.crs is None: raise ValueError("The Powai boundary file has no coordinate reference system.")
        geom=gdf.to_crs(4326).geometry.union_all().__geo_interface__
        ref,transform,crs,projected_geom,pixel_km2=_read_reference_grid(payloads["earlier_green"],geom)
        inside=geometry_mask([projected_geom],out_shape=ref.shape,transform=transform,invert=True)
        grid_shape=ref.shape
        dates=[]
        for date_key in ("earlier","later"):
            arrays={}
            for role in roles:
                name=f"{date_key}_{role}"
                if date_key=="earlier" and role=="green": arrays[role]=ref
                else: arrays[role]=_warp_uploaded_band(payloads[name],grid_shape,transform,crs)
            area,mask_arr,valid,rgb,index,preview_note=_classify_uploaded(arrays,kind,threshold,inside)
            if not valid.any(): raise ValueError(f"The uploaded {date_key} bands contain no valid pixels inside the Powai boundary. Check AOI coverage, nodata, and CRS.")
            year=start_year if date_key=="earlier" else end_year
            dates.append({"area":area*pixel_km2,"mask":mask_arr,"valid":valid,"rgb":rgb,"index":index,"year":year,"date":None,"scene":"User-uploaded bands"})
        before,after=dates
        valid_both=before["valid"]&after["valid"]&inside
        change_codes=np.where(valid_both,before["mask"].astype("uint8")+10*after["mask"].astype("uint8"),255).astype("uint8")
        change_image=np.full((*change_codes.shape,3),[220,220,220],dtype="uint8")
        change_image[change_codes==0]=[232,236,233]; change_image[change_codes==1]=[235,74,86]
        change_image[change_codes==10]=[45,150,235]; change_image[change_codes==11]=[45,185,115]
        denominator=max(int(valid_both.sum()),1)
        change_stats={str(code):round(float(np.sum(change_codes[valid_both]==code)/denominator*100),2) for code in [0,1,10,11]}
        change_areas={"unchanged":round(float(np.sum(valid_both&(change_codes==11))*pixel_km2),4),"reduced":round(float(np.sum(valid_both&(change_codes==1))*pixel_km2),4),"increased":round(float(np.sum(valid_both&(change_codes==10))*pixel_km2),4)}
        earlier_area=round(before["area"],4); later_area=round(after["area"],4); change=later_area-earlier_area
        binary_stats={"earlier_pct":round(float(before["mask"][before["valid"]].mean()*100),2),"later_pct":round(float(after["mask"][after["valid"]].mean()*100),2)}
        def scene_preview(entry):
            clean=np.where(np.isfinite(entry["rgb"]),entry["rgb"],np.nan)
            return png64(display_rgb(clean,None,kind,inside))
        method=f"User-uploaded {satellite.title()} single-band GeoTIFFs; {preview_note} Cloud masking is not automatic for custom bands; nodata and Powai AOI masked. All date bands resampled to the earlier Green grid."
        return {"analysis":kind,"metric":"water_area_km2" if kind=="water" else "builtup_area_km2","earlier":{"year":start_year,"area_km2":earlier_area,"date":None,"scene":"User-uploaded bands","cloud":None},"later":{"year":end_year,"area_km2":later_area,"date":None,"scene":"User-uploaded bands","cloud":None},"change_km2":round(change,4),"change_percent":round(change/earlier_area*100,2) if earlier_area else None,"warnings":["Custom uploaded bands are not automatically cloud-masked. Use clear-sky, consistently processed bands."],"change_legend":"0 non-target in both dates · 1 target loss · 10 target gain · 11 target unchanged · gray nodata","binary_stats":binary_stats,"change_stats":change_stats,"change_areas_km2":change_areas,"change_preview":png64(change_image),"previews":{"earlier":scene_preview(before),"later":scene_preview(after),"index_earlier":render_index(before["index"],before["valid"],inside),"index_later":render_index(after["index"],after["valid"],inside),"binary_earlier":render_binary(before["mask"],before["valid"],inside,kind),"binary_later":render_binary(after["mask"],after["valid"],inside,kind)},"method":method}
    except Exception as e:
        raise HTTPException(400,str(e))











































