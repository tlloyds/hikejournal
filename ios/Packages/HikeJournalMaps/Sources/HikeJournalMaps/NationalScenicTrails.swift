import Foundation

public struct NationalScenicTrailDefinition: Codable, Equatable, Sendable, Identifiable {
  public let id: String
  public let name: String
  public let shortName: String
  public let states: String
  public let layerURLs: [URL]
  public let isFeatured: Bool
  public let objectIDField: String

  public init(
    id: String,
    name: String,
    shortName: String,
    states: String,
    layerURLs: [URL],
    isFeatured: Bool = false,
    objectIDField: String = "OBJECTID"
  ) {
    self.id = id
    self.name = name
    self.shortName = shortName
    self.states = states
    self.layerURLs = layerURLs
    self.isFeatured = isFeatured
    self.objectIDField = objectIDField
  }

  /// Builds the same bounded, paginated ArcGIS GeoJSON query used by Android.
  public func geoJSONPageURL(layerURL: URL, page: Int) -> URL? {
    guard layerURLs.contains(layerURL), (0..<NationalScenicTrailCatalog.maximumPages).contains(page)
    else {
      return nil
    }
    var components = URLComponents(
      url: layerURL.appendingPathComponent("query"),
      resolvingAgainstBaseURL: false
    )
    components?.queryItems = [
      URLQueryItem(name: "where", value: "1=1"),
      URLQueryItem(name: "outFields", value: objectIDField),
      URLQueryItem(name: "returnGeometry", value: "true"),
      URLQueryItem(name: "outSR", value: "4326"),
      URLQueryItem(name: "f", value: "geojson"),
      URLQueryItem(name: "maxAllowableOffset", value: "0.00005"),
      URLQueryItem(name: "resultRecordCount", value: String(NationalScenicTrailCatalog.pageSize)),
      URLQueryItem(name: "resultOffset", value: String(page * NationalScenicTrailCatalog.pageSize)),
    ]
    return components?.url
  }

  public var sourceAttributions: [MapAttribution] {
    layerURLs.enumerated().compactMap { index, url in
      try? MapAttribution(
        id: "national-scenic-trail:\(id):\(index)",
        title: "\(shortName) trail data",
        url: url
      )
    }
  }
}

public enum NationalScenicTrailCatalog {
  public static let pageSize = 2_000
  public static let maximumPages = 20

  public static let all: [NationalScenicTrailDefinition] = [
    definition(
      id: "appalachian",
      name: "Appalachian Trail",
      shortName: "AT",
      states: "Georgia to Maine",
      urls: [
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0"
      ],
      featured: true
    ),
    definition(
      id: "pacific-crest",
      name: "Pacific Crest Trail",
      shortName: "PCT",
      states: "California · Oregon · Washington",
      urls: [
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCTA_Centerline/FeatureServer/0"
      ],
      featured: true
    ),
    definition(
      id: "continental-divide",
      name: "Continental Divide Trail",
      shortName: "CDT",
      states: "New Mexico to Montana",
      urls: [
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/Continental_Divide_NST_view/FeatureServer/0"
      ],
      featured: true
    ),
    definition(
      id: "florida",
      name: "Florida Trail",
      shortName: "FT",
      states: "Florida",
      urls: [
        "https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0"
      ],
      objectIDField: "FID"
    ),
    definition(
      id: "arizona",
      name: "Arizona Trail",
      shortName: "AZT",
      states: "Arizona",
      urls: [
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/3"
      ]
    ),
    definition(
      id: "ice-age",
      name: "Ice Age Trail",
      shortName: "IAT",
      states: "Wisconsin",
      urls: [
        "https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Segments_CR/FeatureServer/0"
      ]
    ),
    definition(
      id: "natchez-trace",
      name: "Natchez Trace Trail",
      shortName: "NATT",
      states: "Alabama · Mississippi · Tennessee",
      urls: [
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NATT_TRANS_NSTTrail/FeatureServer/0"
      ]
    ),
    definition(
      id: "new-england",
      name: "New England Trail",
      shortName: "NET",
      states: "Connecticut · Massachusetts",
      urls: [
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NEEN_BND_NationalScenicTrailCenterline_ln/FeatureServer/0"
      ],
      objectIDField: "FID"
    ),
    definition(
      id: "north-country",
      name: "North Country Trail",
      shortName: "NCT",
      states: "North Dakota to Vermont",
      urls: [
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/nct_public/FeatureServer/2",
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/agol_sht_public/FeatureServer/1",
      ]
    ),
    definition(
      id: "pacific-northwest",
      name: "Pacific Northwest Trail",
      shortName: "PNT",
      states: "Montana · Idaho · Washington",
      urls: [
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0"
      ],
      objectIDField: "FID"
    ),
    definition(
      id: "potomac-heritage",
      name: "Potomac Heritage Trail",
      shortName: "PHT",
      states: "Virginia · DC · Maryland · Pennsylvania",
      urls: [
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POHE_Trail_Centerline_FTDS_view/FeatureServer/0"
      ]
    ),
  ]

  public static func definition(id: String) -> NationalScenicTrailDefinition? {
    all.first { $0.id == id }
  }

  public static func selected(ids: Set<String>) -> [NationalScenicTrailDefinition] {
    all.filter { ids.contains($0.id) }
  }

  private static func definition(
    id: String,
    name: String,
    shortName: String,
    states: String,
    urls: [String],
    featured: Bool = false,
    objectIDField: String = "OBJECTID"
  ) -> NationalScenicTrailDefinition {
    NationalScenicTrailDefinition(
      id: id,
      name: name,
      shortName: shortName,
      states: states,
      layerURLs: urls.compactMap(URL.init(string:)),
      isFeatured: featured,
      objectIDField: objectIDField
    )
  }
}
