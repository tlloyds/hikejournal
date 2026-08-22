import Foundation
import XCTest

@testable import HikeJournalMaps

final class NationalScenicTrailCatalogTests: XCTestCase {
  func testCatalogMatchesAndroidProductionDefinitions() throws {
    let catalog = NationalScenicTrailCatalog.all
    XCTAssertEqual(catalog.count, 11)
    XCTAssertEqual(Set(catalog.map(\.id)).count, 11)
    XCTAssertEqual(
      Set(catalog.filter(\.isFeatured).map(\.id)),
      ["appalachian", "pacific-crest", "continental-divide"]
    )
    XCTAssertEqual(
      NationalScenicTrailCatalog.definition(id: "north-country")?.layerURLs.map(\.absoluteString),
      [
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/nct_public/FeatureServer/2",
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/agol_sht_public/FeatureServer/1",
      ]
    )
    XCTAssertEqual(NationalScenicTrailCatalog.definition(id: "florida")?.objectIDField, "FID")
    XCTAssertEqual(NationalScenicTrailCatalog.definition(id: "new-england")?.objectIDField, "FID")
    XCTAssertEqual(
      NationalScenicTrailCatalog.definition(id: "pacific-northwest")?.objectIDField, "FID")
    XCTAssertTrue(catalog.flatMap(\.layerURLs).allSatisfy { $0.scheme == "https" })
  }

  func testEveryAndroidSourceURLIsExact() {
    let allURLs = NationalScenicTrailCatalog.all.flatMap(\.layerURLs).map(\.absoluteString)
    XCTAssertEqual(
      allURLs,
      [
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCTA_Centerline/FeatureServer/0",
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/Continental_Divide_NST_view/FeatureServer/0",
        "https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0",
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/3",
        "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Segments_CR/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NATT_TRANS_NSTTrail/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NEEN_BND_NationalScenicTrailCenterline_ln/FeatureServer/0",
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/nct_public/FeatureServer/2",
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/agol_sht_public/FeatureServer/1",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POHE_Trail_Centerline_FTDS_view/FeatureServer/0",
      ]
    )
  }

  func testArcGISQueryMatchesAndroidPaginationAndBounds() throws {
    let florida = try XCTUnwrap(NationalScenicTrailCatalog.definition(id: "florida"))
    let source = try XCTUnwrap(florida.layerURLs.first)
    let url = try XCTUnwrap(florida.geoJSONPageURL(layerURL: source, page: 3))
    let items = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems)
    let values = Dictionary(
      uniqueKeysWithValues: items.compactMap { item in
        item.value.map { (item.name, $0) }
      })
    XCTAssertTrue(url.path.hasSuffix("/FeatureServer/0/query"))
    XCTAssertEqual(values["where"], "1=1")
    XCTAssertEqual(values["outFields"], "FID")
    XCTAssertEqual(values["returnGeometry"], "true")
    XCTAssertEqual(values["outSR"], "4326")
    XCTAssertEqual(values["f"], "geojson")
    XCTAssertEqual(values["maxAllowableOffset"], "0.00005")
    XCTAssertEqual(values["resultRecordCount"], "2000")
    XCTAssertEqual(values["resultOffset"], "6000")
    XCTAssertNil(florida.geoJSONPageURL(layerURL: source, page: 20))
  }

  func testEachTrailProvidesRequiredSourceAttribution() {
    for trail in NationalScenicTrailCatalog.all {
      XCTAssertEqual(trail.sourceAttributions.count, trail.layerURLs.count)
      XCTAssertTrue(trail.sourceAttributions.allSatisfy { $0.url.scheme == "https" })
    }
  }
}
