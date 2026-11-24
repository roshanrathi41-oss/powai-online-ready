Powai Change Observatory — local analysis service

Supported comparison years in the website: 2014 through 2026.
Satellite choices: Landsat Collection 2 Level-2 (2014–2024) and Sentinel-2 L2A (2015 onward through 2026). Sentinel-2 is not available for 2014; the service returns a clear availability message. Some year/month/cloud combinations may also have no suitable scene; the service reports that rather than using another date silently.

The service searches Microsoft Planetary Computer, signs public asset URLs, applies QA cloud masking, clips to the supplied Powai boundary, calculates water (MNDWI > 0) or built-up (ENDISI > 0), and returns scene previews and pixel-area estimates. Results are scene-specific threshold estimates; include scene dates, sensor, month, cloud limit, and method in reports.

Run from this folder in the activated conda environment:
  python -m uvicorn app:app --host 127.0.0.1 --port 8000

The service returns a coded change map: 1 = water-to-non-water, 10 = non-water-to-water, 11 = water in both dates, 0 = non-water in both dates. Light gray marks cloud-masked or out-of-AOI pixels. The selected class follows the active Water/Built-up tab.

