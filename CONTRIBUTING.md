# Contributing

Thanks for your interest in improving the Satellite Data Search Toolkit. This is a research tool, and contributions of all sizes are welcome — bug reports, documentation fixes, new sensors, or new pipeline stages.

## Getting set up

```bash
git clone https://github.com/SAY70/satellite-data-search.git
cd satellite-data-search
pip install -r requirements.txt
```

You'll need your own free accounts before anything runs:

- **Google Earth Engine** — register a Cloud project at [code.earthengine.google.com/register](https://code.earthengine.google.com/register). The project ID in the committed notebooks belongs to the original author and won't work for you.
- **NASA Earthdata** — [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov/), only needed to test the download step.

[docs/pdf/00_Getting_Started.pdf](docs/pdf/00_Getting_Started.pdf) walks through the whole setup.

Run the app with `streamlit run app.py`, or work through the numbered notebooks.

## How the code is organized

The important thing to know: **the notebooks and the dashboard are both thin layers over the same modules.** There is one implementation of each pipeline step, not two.

| Module | Responsibility |
|---|---|
| `sat_search.py` | Multi-mission search (Earth Engine + NASA CMR) |
| `sat_download.py` | Scene download (clipped from EE, or full files from the archive) |
| `sat_forecast.py` | Empirical revisit-pattern detection and forecasting |
| `sat_orbit.py` | Live TLE fetch and orbit propagation |
| `aoi_export.py` | AOI import/export (GeoJSON/KML/KMZ) |
| `app.py` | Streamlit UI only — no pipeline logic |

If you're fixing pipeline behavior, fix it in the module. If you change a module's behavior, check whether the corresponding notebook still reads correctly.

## Adding a new sensor

Most new-sensor work happens in `sat_search.py`:

1. **Define its products.** Add a `..._PRODUCTS` dict following the existing pattern. Earth Engine products need `collection_id`, `resolution_m`, `level`, and a `properties` map from output column → EE property name. CMR products need `provider`, `short_names`, `id_regex` (or `None`), `resolution_m`, and `level`.
2. **Register it** in `SENSOR_PRODUCTS` as `"Sensor Name": (ee_products, cmr_products)` — either half can be `{}`.
3. **Give it a color** in `SENSOR_COLORS` so its footprints are distinguishable on the map.
4. **If it's downloadable from Earth Engine**, add its product label → collection ID mapping to `EE_COLLECTION_BY_PRODUCT` in `sat_download.py`.

The `id_regex` field is worth understanding: any named capture groups become DataFrame columns automatically, which is how Sentinel-1 gets `instrument_mode`/`polarization` and NISAR gets `orbit_pass` without special-casing either.

## Regenerating documentation

The PDFs and README diagrams are generated, not hand-edited:

```bash
python docs/generate_guides.py      # -> docs/pdf/*.pdf
python docs/generate_diagrams.py    # -> docs/images/*.svg
```

Edit the content in those scripts and re-run them; don't edit the output files directly.

## Testing your changes

There's no automated test suite yet (contributions welcome). At minimum, before opening a PR:

- Run the affected notebook end to end, or the affected tab in the app, against a real AOI.
- If you touched search or download, confirm your change works against the live APIs — most bugs in this codebase have come from real-world API behavior, not logic errors.
- Verify the app still starts cleanly: `streamlit run app.py`.

## Reporting bugs

Open an issue with:

- What you ran (notebook or app, which step)
- The AOI and date range, if relevant
- The full error message and traceback
- Whether the sensor genuinely has data for that AOI/date range — a sensor returning zero results is often correct behavior, not a bug. Sentinel-1 is tasked rather than systematic, and Sentinel-6 is ocean-only, so both legitimately return nothing for many land AOIs.

## Pull requests

- Keep changes focused; one concern per PR.
- Match the existing style — no linter is enforced, but the codebase avoids unnecessary comments and keeps functions small and readable.
- Don't commit credentials, downloaded data, or generated output. Check `.gitignore` if you're adding a new kind of artifact.

## Code of conduct

Be respectful and constructive. Assume good faith.

## License

By contributing, you agree that your contributions will be licensed under the [GPL-3.0](LICENSE) license that covers this project.
