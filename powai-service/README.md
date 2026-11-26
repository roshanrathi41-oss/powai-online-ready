# Powai Change Observatory

The **Powai Change Observatory** is a web-based remote-sensing project for comparing water surface and built-up land in the Powai study area, Mumbai. It retrieves satellite scenes or accepts user-supplied raster bands, calculates spectral indices, classifies each date, maps pixel-level change, and reports area statistics.

## Open the website

**Live website:** [https://powai-change-observatory.onrender.com](https://powai-change-observatory.onrender.com)

Open that link in a browser to use the deployed app. The service runs on Render's free plan and may take around 50 seconds or longer to respond after a period of inactivity. If the first page or analysis takes time, wait for the service to wake and retry. The API health check is available at [https://powai-change-observatory.onrender.com/api/health](https://powai-change-observatory.onrender.com/api/health).

## Project question

How did water surface and built-up land change within the supplied Powai area between selected dates? The original assignment asks for a summer comparison of 2014 and 2024, including built-up area and Powai Lake water surface area. The app currently lets users select years from **2014 through 2026** and defaults to **2017 before / 2026 after**, **March**, and **Sentinel-2**.

The website's current year range and default comparison do not, by themselves, constitute the original 2014–2024 assignment result. For a consistent 2014–2024 comparison, select those years and the same month, and use Landsat for both dates. Sentinel-2 did not exist in 2014: Sentinel-2A launched on 23 June 2015, with its first image acquired on 27 June 2015. A usable Powai scene can be later depending on coverage and cloud conditions. [ESA mission and launch information](https://www.esa.int/missions/about-us/directorates/earth-observation-programmes/copernicus/sentinel-2)

## What the website does

The interface has two analysis tabs:

- **Water changes** maps surface water and calculates water area.
- **Built-up changes** maps built-up pixels and calculates built-up area.

For either analysis, the user chooses **Auto-generated** or **Use your own layers**. Auto-generated mode searches the Microsoft Planetary Computer STAC catalog for satellite imagery. The user selects the year pair, month, satellite collection, cloud cover limit, and (for built-up) the ENDISI threshold. The app prefers the least-cloudy scene that covers at least 98% of the Powai boundary. Sentinel-2 searches are restricted to tile **43QBB**.

The result view includes before and after satellite previews, index maps, binary classification maps, a change-detection map with a legend, area summaries, occupied percentages, coverage and change bar charts, and a map centered on the Powai area. The exact scene IDs, dates, and cloud values used for an auto-generated result appear in the status text below the charts. Save that information with each reported result.

### Accuracy assessment

The website estimates mapped area and change. Its current analysis API does **not** calculate overall accuracy or Cohen's kappa automatically. Accuracy figures and spatial validation maps shown in the accompanying report/presentation come from a separate reference-sample assessment. To make those figures reproducible, retain the classified map, reference labels/sample locations, index and threshold, year/sensor, confusion-matrix counts, overall-accuracy calculation, and kappa calculation together. Do not treat the app's area estimates as accuracy scores.

## Methods

### Water mapping: NDWI

The app calculates the Normalized Difference Water Index:

```text
NDWI = (Green − NIR) / (Green + NIR)
```

Water is classified where **NDWI > 0**. In Sentinel-2 mode, the app also includes pixels labelled as water in the Scene Classification Layer (SCL class 6). A small binary opening removes isolated classification noise. For Sentinel-2 water analysis, the native 10 m B03 Green and B08 NIR bands are used on a 10 m grid.

MNDWI is not the app's water-classification rule. MNDWI uses Green and SWIR1; Sentinel-2 B11 SWIR1 is 20 m while B03 is 10 m, so the bands need grid alignment. MNDWI is also used as a component of the implemented ENDISI built-up calculation.

### Built-up mapping: ENDISI

The app uses the Enhanced Normalized Difference Impervious Surface Index (ENDISI) implementation below. The scene-derived coefficient `α` is estimated from clear, non-water pixels. The default built-up rule is **ENDISI > −0.32**; users can adjust the threshold in the interface. The app excludes pixels classified as water from the built-up mask.

```text
MNDWI = (Green − SWIR1) / (Green + SWIR1)
R     = SWIR1 / SWIR2
ENDISI = [Blue − α × (R + MNDWI²)] / [Blue + α × (R + MNDWI²)]
```

For Sentinel-2 built-up analysis, B02 Blue, B03 Green, B04 Red, B08 NIR, B11 SWIR1, and B12 SWIR2 are aligned to the 20 m B11 grid. The implementation computes the ENDISI calibration coefficient from source band values, so report the chosen sensor, scene IDs, threshold, and dates with results. The classification is a threshold-based estimate, not a parcel-level or building-footprint survey.

### Imagery, masking, and area

- **Sentinel-2:** Planetary Computer collection `sentinel-2-l2a`; tile 43QBB; water output at 10 m and built-up output at 20 m.
- **Landsat:** Planetary Computer collection `landsat-c2-l2`; Collection 2 Level-2 surface reflectance; output at 30 m.
- **Scene selection:** same selected month for both years; cloud-cover limit applied; scene must cover at least 98% of the Powai AOI; among qualifying scenes, the app chooses the lowest cloud-cover scene.
- **Preprocessing:** sensor-specific cloud, shadow, and snow masking; clip to the supplied Powai boundary; compare only pixels valid in both dates.
- **Area:** classified pixel count × pixel area, converted to square kilometres (km²). Percent occupied is calculated within the valid pixels for that date.

The selected month should represent a comparable seasonal condition in both years. Clouds, shadows, haze, water level, sensor resolution, and threshold choice can change the result. Select the same sensor for both years where the archive allows it; 2014 requires Landsat.

### Change-detection codes

The app encodes the earlier target mask as 0 or 1 and adds ten times the later target mask. It does this separately for water or built-up pixels:

| Code | Meaning |
| --- | --- |
| 0 | Non-target in both dates |
| 1 | Target in the earlier date only: water/built-up reduced or lost |
| 10 | Target in the later date only: water/built-up increased or gained |
| 11 | Target in both dates: unchanged target |

Cloud/no-data pixels and pixels outside the AOI are excluded from the transition calculation. Change areas are reported in km². “Reduced” and “increased” refer to the selected target class, not necessarily a verified physical cause.

## Using the website

1. Open the [live website](https://powai-change-observatory.onrender.com).
2. Select **Water changes** or **Built-up changes**.
3. Choose **Auto-generated** to search the imagery archive, or **Use your own layers** to upload GeoTIFF bands.
4. Set the earlier and later years. For the original assignment, use 2014 and 2024, choose the same summer month, and choose Landsat for both.
5. Select the same month for both dates, the satellite collection, and a cloud cover limit. For built-up, review the ENDISI threshold (default −0.32).
6. Click **Run analysis** and wait for scene search, data download, masking, index calculation, and map generation to finish. Large uploads and the first request after inactivity may take longer.
7. Review all preview, index, binary, and change maps alongside the area values and charts. Read the legend and result status before interpreting a map.
8. Record the run details using the result template below. For a presentation, capture the completed result maps and charts, not just the setup screen.

### Uploading your own layers

Upload **one single-band GeoTIFF per band prompt for each date**. A multi-band stack is not accepted as one file. The entered years label the uploaded dates; they do not modify or verify the imagery dates.

| Analysis | Required bands for each date | Sentinel-2 band codes | Landsat 8/9 band codes |
| --- | --- | --- | --- |
| Water (NDWI) | Green, NIR | B03, B08 | B3, B5 |
| Built-up (ENDISI) | Blue, Green, Red, NIR, SWIR1, SWIR2 | B02, B03, B04, B08, B11, B12 | B2, B3, B4, B5, B6, B7 |

Prepare uploads as georeferenced GeoTIFFs with CRS metadata, matching geographic coverage, and consistent units/scaling across both dates. The app aligns later bands to the earlier Green grid. Use a projected CRS in metres; **EPSG:32643 (WGS 84 / UTM zone 43N)** is recommended. Clip bands to the Powai study area before upload to reduce transfer and processing time. The automated cloud/shadow/snow masks do not apply to custom uploads, so use clear-sky or already masked data. The server code validates a maximum of 512 MB per band and 4 GB total per analysis; browser, hosting-provider, memory, or timeout limits may be lower in practice.

## Running the website locally

The deployed link is easiest for normal use. To run the source project on Windows:

1. Install Miniforge or Anaconda with conda, then open its Prompt (or a VS Code terminal where `conda` works).
2. Change directory to the downloaded project folder that contains `environment.yml` and `powai-service`.
3. Create the environment once:

   ```bat
   conda env create -f environment.yml
   ```

   If the `powai` environment already exists, skip environment creation.

4. Activate the environment:

   ```bat
   conda activate powai
   ```

5. Start the service from the `powai-service` folder:

   ```bat
   cd powai-service
   python -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```

6. Keep the terminal open and browse to [http://127.0.0.1:8000](http://127.0.0.1:8000). Do not open `index.html` directly as a file; the page needs the running API service.
7. Stop the local service with **Ctrl+C** in the terminal.

The included `Start Powai Service.bat` is a Windows shortcut to activate and launch the service. Its configured Miniforge path may need editing if Miniforge is installed somewhere else. Keep the `study-area` folder and all shapefile components together: `.shp`, `.shx`, `.dbf`, `.prj`, and `.cpg`.

## Software and services

- **Front end:** `index.html`, with HTML, CSS, JavaScript, Leaflet/MapLibre map interface, controls, result panels, legends, and charts.
- **Back end:** `powai-service/app.py`, a Python FastAPI service that queries satellite scenes, processes rasters, computes indices, and returns JSON plus map previews.
- **Study-area input:** `powai-service/study-area/outline_shape.shp` and its accompanying shapefile files.
- **Imagery catalogue:** Microsoft Planetary Computer STAC API; the service uses its public catalogue and asset signing SDK.
- **Deployment:** Render web service configured by `Dockerfile`, `environment.yml`, and `render.yaml`. `render.yaml` currently sets `autoDeploy: false`, so pushing code to GitHub alone does not publish a new version. Use Render **Manual Deploy → Deploy latest commit** after pushing changes.

Useful service endpoints:

- `/` — website
- `/api/health` — service and study boundary status
- `/api/study-area` — study boundary as GeoJSON
- `/api/analyze` — automatic imagery analysis
- `/api/analyze/upload` — analysis using uploaded bands

## Files in this project package

| File or folder | Purpose |
| --- | --- |
| `index.html` | Website front end |
| `powai-service/app.py` | Analysis API and raster processing |
| `powai-service/requirements.txt` | Python service dependencies |
| `environment.yml` | Conda environment definition |
| `powai-service/Start Powai Service.bat` | Windows local start shortcut |
| `powai-service/study-area/` | Powai AOI shapefile and supporting files |
| `Dockerfile`, `render.yaml` | Render deployment configuration |
| `accuracy_images/`, `index_comparison_images/` | Supporting accuracy and index-comparison figures, where included |
| `Powai_Project_Complete_Guide.docx` | Expanded project explanation, where included |

The exact files present depend on the ZIP or GitHub snapshot being used. Keep the source code, study boundary components, and configuration files together for local execution and deployment.

## Recording a result for reproducibility

Complete one record for each water or built-up run and retain it with the corresponding maps, charts, and screenshots.

```text
Analysis: Water / Built-up
Mode: Auto-generated / Own layers
Earlier year and scene/date:
Later year and scene/date:
Sensor and collection:
Month and season:
Sentinel tile (if applicable): 43QBB
Maximum cloud cover (%):
Index and threshold: NDWI > 0 / ENDISI > ______
Pixel resolution:
Input files (for own layers):
Earlier area (km²):
Later area (km²):
Net change (km² and %):
Transition areas (unchanged / reduced / increased, km²):
Warnings or no-data notes:
Output screenshots/maps/charts:
Date run:
```

Use the **scene IDs and actual dates returned by the app**, not just the year labels selected in the controls. For custom layers, list every band filename for both dates. This record satisfies the project requirement to state the input files and parameters associated with each result.

## Suggested academic submission ZIP contents

Include these items when preparing the final submission:

1. Presentation slides with screenshots of final website results.
2. Source code and deployment/local-run files: `index.html`, `powai-service/app.py`, `powai-service/requirements.txt`, `environment.yml`, `Dockerfile`, `render.yaml`, and the start script.
3. Sample input data: the AOI shapefile components and any sample satellite/band data that you are allowed to redistribute.
4. Results: exported maps, screenshots, charts, and area summaries for each reported run.
5. This README, plus a completed result record for every output set.

Do not include credentials or private access tokens. The website uses public imagery access through the Planetary Computer SDK.

## Known limitations and interpretation

- A scene must meet the cloud filter and cover nearly all of the AOI. The app may report no scene for a chosen month even if imagery exists elsewhere or at a higher cloud level.
- Sentinel-2 cannot supply a 2014 image. For a 2014–2024 comparison, Landsat is needed for both dates if sensor consistency is required.
- The two satellite collections have different pixel sizes. Use one collection for both dates where possible, and interpret mixed-sensor results cautiously.
- Threshold methods are sensitive to season, atmospheric conditions, pixel size, and built-up/water mixtures. Visual inspection and ground-reference validation are important.
- User-uploaded layers are not automatically cloud-masked. The app assumes the user supplied compatible bands and correctly assigned each band to the requested prompt.
- The map basemap depends on an external tile service and internet access. A basemap is contextual; the satellite analysis outputs come from the selected satellite scenes or uploaded rasters.
- The application estimates surface class area inside the supplied AOI. It does not establish why change occurred or replace field verification.
- The original assignment's 2014 and 2024 summer comparison should be reported separately from other year-pairs explored through the website.

## References

- McFeeters, S. K. (1996). *The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features.* International Journal of Remote Sensing, 17(7), 1425–1432. https://doi.org/10.1080/01431169608948714
- Xu, H. (2006). *Modification of normalised difference water index (NDWI) to enhance open water features in remotely sensed imagery.* International Journal of Remote Sensing, 27(14), 3025–3033. https://doi.org/10.1080/01431160600589179
- Chen, X. et al. (2019). *A new index for mapping built-up and bare land areas from Landsat-8 OLI data.* Remote Sensing of Environment, 232, 111297. https://doi.org/10.1016/j.rse.2019.111297
- European Space Agency. [Sentinel-2 mission information](https://www.esa.int/missions/about-us/directorates/earth-observation-programmes/copernicus/sentinel-2).
- Microsoft Planetary Computer. [STAC API](https://planetarycomputer.microsoft.com/docs/overview/about/).
