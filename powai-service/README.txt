POWAI CHANGE OBSERVATORY — ANALYSIS SERVICE

Auto-generated mode searches Microsoft Planetary Computer, signs public image assets, applies sensor cloud masks, clips to the supplied Powai boundary, and returns satellite, index, binary, change maps and area charts.

Use your own layers mode accepts one single-band GeoTIFF per band prompt, for both the earlier and later years. Files must have georeferencing and a CRS. Use rasters clipped to the Powai study area, projected in metres (EPSG:32643 recommended), and consistently scaled for their sensor/date. Uploaded layers are aligned to the earlier Green band. Custom uploads are not automatically cloud-masked; use clear-sky imagery or a pre-masked raster.

Water (NDWI): upload Green and NIR for each date.
- Sentinel-2: B03 Green and B08 NIR.
- Landsat 8/9: B3 Green and B5 NIR.

Built-up (ENDISI): upload Blue, Green, Red, NIR, SWIR-1, and SWIR-2 for each date.
- Sentinel-2: B02, B03, B04, B08, B11, and B12.
- Landsat 8/9: B2, B3, B4, B5, B6, and B7.
ENDISI uses Blue, Green, SWIR-1, and SWIR-2; NIR is used for water exclusion and Red/Green/Blue supply the preview.

A single-band GeoTIFF file is required for each prompt. Do not upload a multi-band stack in one input. Files are limited to 25 MB each and 120 MB per analysis upload. The years entered are labels for the uploaded dates; they do not change the images.

Run locally in the activated conda environment:
  python -m uvicorn app:app --host 127.0.0.1 --port 8000
