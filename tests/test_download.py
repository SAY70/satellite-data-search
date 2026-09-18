"""Tests for download path handling and the search/download product contract."""

import pandas as pd
import pytest

import sat_download
import sat_search


class TestSafeName:
    @pytest.mark.parametrize("product,expected", [
        ("Sentinel-1 GRD High-Res (Dual-pol)", "Sentinel-1_GRD_High-Res_Dual-pol"),
        ("MODIS Terra Vegetation (NDVI/EVI)", "MODIS_Terra_Vegetation_NDVI-EVI"),
        ("Landsat HLS L30", "Landsat_HLS_L30"),
    ])
    def test_converts_product_to_folder_name(self, product, expected):
        assert sat_download.safe_name(product) == expected

    def test_output_has_no_path_separators(self):
        """A '/' in a product name would silently create a nested folder."""
        for product in sat_download.EE_COLLECTION_BY_PRODUCT:
            name = sat_download.safe_name(product)
            assert "/" not in name and "\\" not in name

    def test_output_is_unique_per_product(self):
        """Two products collapsing to one folder would overwrite each other."""
        names = [sat_download.safe_name(p) for p in sat_download.EE_COLLECTION_BY_PRODUCT]
        assert len(names) == len(set(names))


class TestSummarizeDownloads:
    def test_reports_files_with_product_and_size(self, tmp_path):
        product_dir = tmp_path / "Sentinel-1_SLC"
        product_dir.mkdir()
        (product_dir / "scene.zip").write_bytes(b"x" * (2 * 1024 * 1024))

        out = sat_download.summarize_downloads(tmp_path)

        assert len(out) == 1
        assert out.iloc[0]["product"] == "Sentinel-1_SLC"
        assert out.iloc[0]["file"] == "scene.zip"
        assert out.iloc[0]["size_mb"] == pytest.approx(2.0, rel=1e-3)

    def test_totals_across_products(self, tmp_path):
        for product in ["A", "B"]:
            d = tmp_path / product
            d.mkdir()
            (d / "f.tif").write_bytes(b"x" * (1024 * 1024))

        out = sat_download.summarize_downloads(tmp_path)
        assert len(out) == 2
        assert out["size_mb"].sum() == pytest.approx(2.0, rel=1e-3)

    def test_missing_directory_returns_empty_frame_with_columns(self, tmp_path):
        """The app reads these columns before anything has been downloaded."""
        out = sat_download.summarize_downloads(tmp_path / "does_not_exist")
        assert out.empty
        assert list(out.columns) == ["product", "file", "size_mb"]


def test_ee_downloadable_products_exist_in_search():
    """sat_download looks products up by the exact label sat_search produces.

    If a label is edited in one module and not the other, downloads raise
    KeyError at runtime -- after the user has already run a search.
    """
    search_labels = set()
    for ee_products, cmr_products in sat_search.SENSOR_PRODUCTS.values():
        search_labels.update(ee_products)
        search_labels.update(cmr_products)

    unknown = set(sat_download.EE_COLLECTION_BY_PRODUCT) - search_labels
    assert not unknown, f"download labels not produced by any search: {unknown}"


def test_ee_search_products_are_all_downloadable():
    """Every Earth Engine product the search returns should be downloadable."""
    ee_search_labels = set()
    for ee_products, _ in sat_search.SENSOR_PRODUCTS.values():
        ee_search_labels.update(ee_products)

    missing = ee_search_labels - set(sat_download.EE_COLLECTION_BY_PRODUCT)
    assert not missing, f"searchable EE products with no download mapping: {missing}"


def test_collection_ids_match_between_modules():
    """The same product must point at the same Earth Engine collection in both places."""
    for ee_products, _ in sat_search.SENSOR_PRODUCTS.values():
        for label, cfg in ee_products.items():
            download_id = sat_download.EE_COLLECTION_BY_PRODUCT.get(label)
            assert download_id == cfg["collection_id"], (
                f"{label}: search uses {cfg['collection_id']}, download uses {download_id}"
            )
