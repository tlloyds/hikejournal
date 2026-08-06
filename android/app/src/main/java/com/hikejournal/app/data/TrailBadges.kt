package com.hikejournal.app.data

enum class BadgeCategory(val label: String, val description: String) {
    Hiking("Hiking", "Milestones for showing up, season after season."),
    Distance("Distance", "Lifetime miles and the days that went farther."),
    Quests("Field quests", "Completed targets and less-often-reported finds."),
    FieldGuide("Field guide", "New species added to your personal archive."),
    Specialties("Specialties", "Deeper knowledge across the living world."),
}

enum class BadgeFinish {
    Bronze,
    Silver,
    Gold,
    Evergreen,
}

enum class BadgeSymbol {
    Boot,
    Mountain,
    Route,
    Flag,
    Rare,
    Compass,
    Plant,
    Mammal,
    Fungi,
    Bird,
    Insect,
}

enum class BadgeMetric {
    HikeCount,
    TotalMiles,
    LongestHike,
    CompletedQuests,
    RareFinds,
    SpeciesCount,
    Plants,
    Mammals,
    Fungi,
    Birds,
    Insects,
}

data class TrailBadgeDefinition(
    val id: String,
    val title: String,
    val requirement: String,
    val category: BadgeCategory,
    val metric: BadgeMetric,
    val target: Double,
    val finish: BadgeFinish,
    val symbol: BadgeSymbol,
)

data class TrailBadge(
    val definition: TrailBadgeDefinition,
    val current: Double,
) {
    val earned: Boolean get() = current >= definition.target
    val progress: Float
        get() = (current / definition.target).coerceIn(0.0, 1.0).toFloat()
}

data class SpeciesTypeCounts(
    val total: Int,
    val plants: Int,
    val animals: Int,
    val mammals: Int,
    val birds: Int,
    val insects: Int,
    val fungi: Int,
)

fun speciesTypeCounts(species: List<SpeciesRecord>): SpeciesTypeCounts {
    val distinctSpecies = species.distinctBy { it.taxonId?.toString() ?: it.key }
    fun hasIconicTaxon(species: SpeciesRecord, vararg names: String): Boolean {
        val normalized = species.iconicTaxonName.trim().lowercase()
        return normalized in names.map(String::lowercase).toSet()
    }

    val plants = distinctSpecies.count { hasIconicTaxon(it, "plantae", "plant") }
    val fungi = distinctSpecies.count { hasIconicTaxon(it, "fungi", "fungus") }
    val mammals = distinctSpecies.count { hasIconicTaxon(it, "mammalia", "mammal") }
    val birds = distinctSpecies.count { hasIconicTaxon(it, "aves", "bird") }
    val insects = distinctSpecies.count { hasIconicTaxon(it, "insecta", "insect") }
    val animalTaxa = setOf(
        "animalia",
        "metazoa",
        "mammalia",
        "mammal",
        "aves",
        "bird",
        "insecta",
        "insect",
        "amphibia",
        "reptilia",
        "actinopterygii",
        "arachnida",
        "mollusca",
        "crustacea",
        "annelida",
        "cnidaria",
        "echinodermata",
    )
    val animals = distinctSpecies.count { it.iconicTaxonName.trim().lowercase() in animalTaxa }
    return SpeciesTypeCounts(
        total = distinctSpecies.size,
        plants = plants,
        animals = animals,
        mammals = mammals,
        birds = birds,
        insects = insects,
        fungi = fungi,
    )
}

private fun badge(
    id: String,
    title: String,
    requirement: String,
    category: BadgeCategory,
    metric: BadgeMetric,
    target: Number,
    finish: BadgeFinish,
    symbol: BadgeSymbol,
) = TrailBadgeDefinition(
    id = id,
    title = title,
    requirement = requirement,
    category = category,
    metric = metric,
    target = target.toDouble(),
    finish = finish,
    symbol = symbol,
)

val TrailBadgeCatalog: List<TrailBadgeDefinition> = listOf(
    badge("hikes_1", "First Footfall", "Log your first hike.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 1, BadgeFinish.Bronze, BadgeSymbol.Boot),
    badge("hikes_5", "Five Trails", "Log 5 hikes.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 5, BadgeFinish.Bronze, BadgeSymbol.Boot),
    badge("hikes_10", "Trail Regular", "Log 10 hikes.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 10, BadgeFinish.Silver, BadgeSymbol.Boot),
    badge("hikes_25", "Seasoned Trekker", "Log 25 hikes.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 25, BadgeFinish.Gold, BadgeSymbol.Mountain),
    badge("hikes_50", "Half-Century Hiker", "Log 50 hikes.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 50, BadgeFinish.Gold, BadgeSymbol.Mountain),
    badge("hikes_100", "Hundred Horizons", "Log 100 hikes.", BadgeCategory.Hiking, BadgeMetric.HikeCount, 100, BadgeFinish.Evergreen, BadgeSymbol.Mountain),

    badge("miles_25", "First 25", "Record 25 lifetime miles.", BadgeCategory.Distance, BadgeMetric.TotalMiles, 25, BadgeFinish.Bronze, BadgeSymbol.Route),
    badge("miles_100", "Century Afoot", "Record 100 lifetime miles.", BadgeCategory.Distance, BadgeMetric.TotalMiles, 100, BadgeFinish.Silver, BadgeSymbol.Route),
    badge("miles_250", "Long Way Home", "Record 250 lifetime miles.", BadgeCategory.Distance, BadgeMetric.TotalMiles, 250, BadgeFinish.Gold, BadgeSymbol.Route),
    badge("miles_500", "Ridgeline 500", "Record 500 lifetime miles.", BadgeCategory.Distance, BadgeMetric.TotalMiles, 500, BadgeFinish.Gold, BadgeSymbol.Route),
    badge("miles_1000", "Thousand-Mile Journal", "Record 1,000 lifetime miles.", BadgeCategory.Distance, BadgeMetric.TotalMiles, 1000, BadgeFinish.Evergreen, BadgeSymbol.Route),
    badge("long_hike_10", "Double Digits", "Complete a hike of at least 10 miles.", BadgeCategory.Distance, BadgeMetric.LongestHike, 10, BadgeFinish.Silver, BadgeSymbol.Mountain),
    badge("long_hike_20", "Endurance Day", "Complete a hike of at least 20 miles.", BadgeCategory.Distance, BadgeMetric.LongestHike, 20, BadgeFinish.Evergreen, BadgeSymbol.Mountain),

    badge("quests_1", "Quest Complete", "Complete every focus find in 1 Field Quest.", BadgeCategory.Quests, BadgeMetric.CompletedQuests, 1, BadgeFinish.Bronze, BadgeSymbol.Flag),
    badge("quests_5", "Field Proven", "Complete 5 Field Quests.", BadgeCategory.Quests, BadgeMetric.CompletedQuests, 5, BadgeFinish.Gold, BadgeSymbol.Flag),
    badge("quests_10", "Quest Naturalist", "Complete 10 Field Quests.", BadgeCategory.Quests, BadgeMetric.CompletedQuests, 10, BadgeFinish.Evergreen, BadgeSymbol.Flag),
    badge("rare_1", "Rare Find", "Log 1 quest species marked less often reported.", BadgeCategory.Quests, BadgeMetric.RareFinds, 1, BadgeFinish.Silver, BadgeSymbol.Rare),
    badge("rare_5", "Rare Company", "Log 5 distinct less-often-reported quest species.", BadgeCategory.Quests, BadgeMetric.RareFinds, 5, BadgeFinish.Gold, BadgeSymbol.Rare),

    badge("species_1", "New Find", "Add your first species to the Field Guide.", BadgeCategory.FieldGuide, BadgeMetric.SpeciesCount, 1, BadgeFinish.Bronze, BadgeSymbol.Compass),
    badge("species_25", "Curious Naturalist", "Log 25 distinct species.", BadgeCategory.FieldGuide, BadgeMetric.SpeciesCount, 25, BadgeFinish.Bronze, BadgeSymbol.Compass),
    badge("species_50", "Field Naturalist", "Log 50 distinct species.", BadgeCategory.FieldGuide, BadgeMetric.SpeciesCount, 50, BadgeFinish.Silver, BadgeSymbol.Compass),
    badge("species_100", "Century of Life", "Log 100 distinct species.", BadgeCategory.FieldGuide, BadgeMetric.SpeciesCount, 100, BadgeFinish.Gold, BadgeSymbol.Compass),
    badge("species_250", "Living Archive", "Log 250 distinct species.", BadgeCategory.FieldGuide, BadgeMetric.SpeciesCount, 250, BadgeFinish.Evergreen, BadgeSymbol.Compass),

    badge("plants_25", "Leaf Scout", "Log 25 distinct plants.", BadgeCategory.Specialties, BadgeMetric.Plants, 25, BadgeFinish.Bronze, BadgeSymbol.Plant),
    badge("plants_50", "Field Botanist", "Log 50 distinct plants.", BadgeCategory.Specialties, BadgeMetric.Plants, 50, BadgeFinish.Silver, BadgeSymbol.Plant),
    badge("plants_100", "Flora Authority", "Log 100 distinct plants.", BadgeCategory.Specialties, BadgeMetric.Plants, 100, BadgeFinish.Evergreen, BadgeSymbol.Plant),
    badge("mammals_25", "Mammal Tracker", "Log 25 distinct mammals.", BadgeCategory.Specialties, BadgeMetric.Mammals, 25, BadgeFinish.Bronze, BadgeSymbol.Mammal),
    badge("mammals_50", "Wildlife Observer", "Log 50 distinct mammals.", BadgeCategory.Specialties, BadgeMetric.Mammals, 50, BadgeFinish.Silver, BadgeSymbol.Mammal),
    badge("mammals_100", "Mammal Steward", "Log 100 distinct mammals.", BadgeCategory.Specialties, BadgeMetric.Mammals, 100, BadgeFinish.Evergreen, BadgeSymbol.Mammal),
    badge("fungi_25", "Mycology Scout", "Log 25 distinct fungi.", BadgeCategory.Specialties, BadgeMetric.Fungi, 25, BadgeFinish.Bronze, BadgeSymbol.Fungi),
    badge("fungi_50", "Field Mycologist", "Log 50 distinct fungi.", BadgeCategory.Specialties, BadgeMetric.Fungi, 50, BadgeFinish.Silver, BadgeSymbol.Fungi),
    badge("fungi_100", "Fungi Authority", "Log 100 distinct fungi.", BadgeCategory.Specialties, BadgeMetric.Fungi, 100, BadgeFinish.Evergreen, BadgeSymbol.Fungi),
    badge("birds_25", "Bird Listener", "Log 25 distinct birds.", BadgeCategory.Specialties, BadgeMetric.Birds, 25, BadgeFinish.Bronze, BadgeSymbol.Bird),
    badge("birds_50", "Avian Observer", "Log 50 distinct birds.", BadgeCategory.Specialties, BadgeMetric.Birds, 50, BadgeFinish.Gold, BadgeSymbol.Bird),
    badge("insects_25", "Insect Eye", "Log 25 distinct insects.", BadgeCategory.Specialties, BadgeMetric.Insects, 25, BadgeFinish.Bronze, BadgeSymbol.Insect),
    badge("insects_50", "Invertebrate Observer", "Log 50 distinct insects.", BadgeCategory.Specialties, BadgeMetric.Insects, 50, BadgeFinish.Gold, BadgeSymbol.Insect),
)

fun calculateTrailBadges(
    hikes: List<Hike>,
    species: List<SpeciesRecord>,
    quests: List<FieldQuest>,
): List<TrailBadge> {
    val outings = hikes.filterNot { it.isStandalone }
    val distinctSpecies = species.distinctBy { it.taxonId?.toString() ?: it.key }
    val completedQuests = quests.count { quest ->
        val focusTaxa = quest.taxa.filter { it.focusOrder != null }
        focusTaxa.isNotEmpty() && focusTaxa.all { it.collected }
    }
    val rareFinds = quests
        .asSequence()
        .flatMap { it.taxa.asSequence() }
        .filter { it.collected && it.frequencyBand.contains("less often", ignoreCase = true) }
        .distinctBy { it.taxonId }
        .count()

    fun iconicCount(vararg names: String): Int {
        val accepted = names.map { it.lowercase() }.toSet()
        return distinctSpecies.count { it.iconicTaxonName.lowercase() in accepted }
    }

    val metrics = mapOf(
        BadgeMetric.HikeCount to outings.size.toDouble(),
        BadgeMetric.TotalMiles to outings.sumOf { (it.distanceMiles ?: 0.0).coerceAtLeast(0.0) },
        BadgeMetric.LongestHike to (outings.maxOfOrNull { (it.distanceMiles ?: 0.0).coerceAtLeast(0.0) } ?: 0.0),
        BadgeMetric.CompletedQuests to completedQuests.toDouble(),
        BadgeMetric.RareFinds to rareFinds.toDouble(),
        BadgeMetric.SpeciesCount to distinctSpecies.size.toDouble(),
        BadgeMetric.Plants to iconicCount("Plantae", "Plant").toDouble(),
        BadgeMetric.Mammals to iconicCount("Mammalia", "Mammal").toDouble(),
        BadgeMetric.Fungi to iconicCount("Fungi", "Fungus").toDouble(),
        BadgeMetric.Birds to iconicCount("Aves", "Bird").toDouble(),
        BadgeMetric.Insects to iconicCount("Insecta", "Insect").toDouble(),
    )
    return TrailBadgeCatalog.map { definition ->
        TrailBadge(definition, metrics.getValue(definition.metric))
    }
}
