package com.hikejournal.app.data

enum class ObservationTypeFilter(val label: String) {
    All("All types"),
    Plants("Plants"),
    Animals("Animals"),
    Birds("Birds"),
    Mammals("Mammals"),
    Insects("Insects"),
    Reptiles("Reptiles"),
    Amphibians("Amphibians"),
    Arachnids("Arachnids"),
    Fungi("Fungi"),
    Fish("Fish"),
    Mollusks("Mollusks"),
    OtherLife("Other life"),
}

private val animalIconicTaxa = setOf(
    "animalia",
    "aves",
    "mammalia",
    "insecta",
    "reptilia",
    "amphibia",
    "arachnida",
    "actinopterygii",
    "mollusca",
)

private val knownIconicTaxa = animalIconicTaxa + setOf("plantae", "fungi")

fun iconicTaxonMatchesObservationType(
    iconicTaxonName: String,
    filter: ObservationTypeFilter,
): Boolean {
    val iconicTaxon = iconicTaxonName.trim().lowercase()
    return when (filter) {
        ObservationTypeFilter.All -> true
        ObservationTypeFilter.Plants -> iconicTaxon == "plantae"
        ObservationTypeFilter.Animals -> iconicTaxon in animalIconicTaxa
        ObservationTypeFilter.Birds -> iconicTaxon == "aves"
        ObservationTypeFilter.Mammals -> iconicTaxon == "mammalia"
        ObservationTypeFilter.Insects -> iconicTaxon == "insecta"
        ObservationTypeFilter.Reptiles -> iconicTaxon == "reptilia"
        ObservationTypeFilter.Amphibians -> iconicTaxon == "amphibia"
        ObservationTypeFilter.Arachnids -> iconicTaxon == "arachnida"
        ObservationTypeFilter.Fungi -> iconicTaxon == "fungi"
        ObservationTypeFilter.Fish -> iconicTaxon == "actinopterygii"
        ObservationTypeFilter.Mollusks -> iconicTaxon == "mollusca"
        ObservationTypeFilter.OtherLife -> iconicTaxon !in knownIconicTaxa
    }
}

fun SpeciesRecord.matchesObservationType(filter: ObservationTypeFilter): Boolean =
    iconicTaxonMatchesObservationType(iconicTaxonName, filter)

fun filterSpeciesByObservationType(
    species: List<SpeciesRecord>,
    filter: ObservationTypeFilter,
): List<SpeciesRecord> =
    if (filter == ObservationTypeFilter.All) species
    else species.filter { it.matchesObservationType(filter) }
