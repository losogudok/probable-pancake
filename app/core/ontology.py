"""Domain ontology for the mining-metallurgy scientific knowledge graph.

Defines entity types, relationship types, trust levels, and the synonym
dictionary for cross-lingual term matching (RU/EN).
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    MATERIAL = "Material"
    PROCESS = "Process"
    EQUIPMENT = "Equipment"
    FACILITY = "Facility"
    EXPERIMENT = "Experiment"
    PUBLICATION = "Publication"
    PATENT = "Patent"
    PROPERTY = "Property"
    PARAMETER = "Parameter"
    EXPERT = "Expert"
    ORGANIZATION = "Organization"
    RECOMMENDATION = "Recommendation"
    TECHNOLOGY = "Technology"
    METHOD = "Method"
    RESULT = "Result"
    CHEMICAL = "Chemical"
    CONDITION = "Condition"


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------

class RelationType(str, Enum):
    USES_MATERIAL = "uses_material"
    USES_REAGENT = "uses_reagent"
    USES_EQUIPMENT = "uses_equipment"
    USES_METHOD = "uses_method"
    REQUIRES = "requires"
    PERFORMED_AT = "performed_at"
    PERFORMED_BY = "performed_by"
    VALIDATED_BY = "validated_by"
    CONTRADICTED_BY = "contradicted_by"
    DESCRIBED_IN = "described_in"
    IMPROVES = "improves"
    DECREASES = "decreases"
    PRODUCES = "produces"
    MEASURED_BY = "measured_by"
    RECOMMENDED_FOR = "recommended_for"
    EXPERT_IN = "expert_in"
    WORKS_AT = "works_at"
    BELONGS_TO = "belongs_to"
    DERIVED_FROM = "derived_from"
    HAS_CONDITION = "has_condition"
    HAS_PARAMETER = "has_parameter"
    HAS_RESULT = "has_result"
    CITES = "cites"
    APPLIES_TO = "applies_to"
    ALTERNATIVE_TO = "alternative_to"


# ---------------------------------------------------------------------------
# Trust / confidence model
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    SCIENTIFIC_ARTICLE = "scientific_article"
    PATENT = "patent"
    INTERNAL_REPORT = "internal_report"
    LAB_JOURNAL = "lab_journal"
    CONFERENCE_PAPER = "conference_paper"
    JOURNAL_ISSUE = "journal_issue"
    REVIEW = "review"
    UNVERIFIED = "unverified"


TRUST_SCORES: dict[SourceType, int] = {
    SourceType.SCIENTIFIC_ARTICLE: 5,
    SourceType.PATENT: 4,
    SourceType.INTERNAL_REPORT: 4,
    SourceType.CONFERENCE_PAPER: 4,
    SourceType.JOURNAL_ISSUE: 4,
    SourceType.REVIEW: 4,
    SourceType.LAB_JOURNAL: 3,
    SourceType.UNVERIFIED: 1,
}


def trust_stars(score: int) -> str:
    return "★" * max(score, 0) + "☆" * (5 - max(score, 0))


# ---------------------------------------------------------------------------
# Geography classification
# ---------------------------------------------------------------------------

class Geography(str, Enum):
    RUSSIA = "Russia"
    CIS = "CIS"
    FOREIGN = "Foreign"
    GLOBAL = "Global"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Domain synonym dictionary (RU <-> EN) for entity normalization
# ---------------------------------------------------------------------------

SYNONYMS: dict[str, list[str]] = {
    # Processes
    "электроэкстракция": ["electrowinning", "электролиз", "electroextraction"],
    "выщелачивание": ["leaching", "кучное выщелачивание", "heap leaching"],
    "флотация": ["flotation", "пенная флотация", "froth flotation"],
    "плавка": ["smelting", "печь взвешенной плавки", "flash smelting"],
    "обжиг": ["roasting", "calcination"],
    "обогащение": ["beneficiation", "mineral processing", "concentration"],
    "сорбция": ["sorption", "adsorption", "ионный обмен", "ion exchange"],
    "экстракция": ["solvent extraction", "жидкостная экстракция"],
    "цементация": ["cementation", "осаждение"],
    "очистка": ["purification", "treatment", "водоочистка"],
    "обессоливание": ["desalination", "demineralization", "опреснение"],
    "фильтрация": ["filtration", "сгущение", "thickening"],
    "сушка": ["drying", "обезвоживание"],
    "измельчение": ["grinding", "crushing", "дробление"],
    "агломерация": ["agglomeration", "окомкование", "pelletizing"],
    "брикетирование": ["briquetting"],
    # Materials / metals
    "никель": ["nickel", "ni"],
    "медь": ["copper", "cu"],
    "кобальт": ["cobalt", "co"],
    "золото": ["gold", "au"],
    "серебро": ["silver", "ag"],
    "платина": ["platinum", "pt"],
    "палладий": ["palladium", "pd"],
    "железо": ["iron", "fe"],
    "цинк": ["zinc", "zn"],
    "свинец": ["lead", "pb"],
    "хром": ["chromium", "cr"],
    "литий": ["lithium", "li"],
    # Materials / compounds
    "сульфат": ["sulfate", "сульфаты"],
    "хлорид": ["chloride", "хлориды"],
    "гипс": ["gypsum", "техногенный гипс"],
    "католит": ["catholyte"],
    "анолит": ["anolyte"],
    "штейн": ["matte", "медный штейн", "никелевый штейн"],
    "шлак": ["slag"],
    "шихта": ["charge", "feed"],
    "концентрат": ["concentrate"],
    "хвосты": ["tailings"],
    # Equipment
    "электролизная ванна": ["electrowinning cell", "электролизер"],
    "печь взвешенной плавки": ["flash smelting furnace", "пвп"],
    "конвертер": ["converter"],
    "мельница": ["mill", "grinding mill"],
    "флотомашина": ["flotation cell", "флотационная машина"],
    # Reagents
    "ксантогенат": ["xanthate"],
    "цианид": ["cyanide"],
    "известь": ["lime", "cao"],
    "серная кислота": ["sulfuric acid", "h2so4"],
    # Environment
    "шахтные воды": ["mine water", "mine drainage"],
    "сточные воды": ["wastewater", "effluent"],
    "so2": ["сернистый газ", "sulfur dioxide"],
    # Climate
    "холодный климат": ["cold climate", "arctic", "крайний север"],
}

# Build reverse lookup: any alias -> canonical (lowercase)
ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in SYNONYMS.items():
    ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for a in aliases:
        ALIAS_TO_CANONICAL[a.lower()] = canonical


def normalize_term(term: str) -> str:
    """Normalize a term to its canonical form using the synonym dictionary."""
    t = term.strip().lower()
    return ALIAS_TO_CANONICAL.get(t, term.strip())


# ---------------------------------------------------------------------------
# Domain keyword sets for heuristic entity tagging
# ---------------------------------------------------------------------------

MATERIAL_KEYWORDS = {
    "никель", "nickel", "медь", "copper", "кобальт", "cobalt", "золото", "gold",
    "серебро", "silver", "платина", "platinum", "палладий", "palladium",
    "железо", "iron", "цинк", "zinc", "свинец", "lead", "хром", "chromium",
    "литий", "lithium", "сульфид", "sulfide", "оксид", "oxide", "сульфат",
    "sulfate", "хлорид", "chloride", "гипс", "gypsum", "штейн", "matte",
    "шлак", "slag", "концентрат", "concentrate", "руда", "ore", "хвосты",
    "tailings", "католит", "catholyte", "анолит", "anolyte",
}

PROCESS_KEYWORDS = {
    "электроэкстракция", "electrowinning", "выщелачивание", "leaching",
    "флотация", "flotation", "плавка", "smelting", "обжиг", "roasting",
    "обогащение", "beneficiation", "сорбция", "sorption", "экстракция",
    "extraction", "цементация", "cementation", "очистка", "purification",
    "обессоливание", "desalination", "фильтрация", "filtration", "сушка",
    "drying", "измельчение", "grinding", "агломерация", "agglomeration",
    "брикетирование", "briquetting", "обеднение", "depletion",
}

EQUIPMENT_KEYWORDS = {
    "ванна", "cell", "печь", "furnace", "конвертер", "converter",
    "мельница", "mill", "флотомашина", "электролизер", "reactor",
    "диафрагма", "diaphragm", "насос", "pump",
}

PARAMETER_KEYWORDS = {
    "температура", "temperature", "скорость", "velocity", "speed", "flow rate",
    "концентрация", "concentration", "давление", "pressure", "плотность",
    "density", "напряжение", "voltage", "ток", "current", "ph", "расход",
    "производительность", "capacity", "выход", "recovery", "извлечение",
    "степень", "efficiency", "кпд",
}

UNIT_PATTERNS = {
    "мг/л", "mg/l", "мг/дм³", "г/л", "g/l", "%", "°c", "°с", "м/с", "m/s",
    "л/мин", "l/min", "м³/ч", "m³/h", "т/сут", "t/day", "bar", "атм",
    "в", "v", "а", "a", "ка", "ka", "мс", "ms", "с", "мин", "ч",
    "руб/м³", "руб/т", "$/t", "usd/t", "моль/л", "mol/l",
}


@dataclass
class Entity:
    """A node in the knowledge graph."""
    id: str
    type: EntityType
    name: str
    canonical: str = ""
    properties: dict = field(default_factory=dict)
    source_ids: list[str] = field(default_factory=list)
    trust: int = 1
    geography: Geography = Geography.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "canonical": self.canonical or self.name,
            "properties": self.properties,
            "source_ids": self.source_ids,
            "trust": self.trust,
            "geography": self.geography.value,
        }


@dataclass
class Relation:
    """An edge in the knowledge graph."""
    source: str
    target: str
    type: RelationType
    properties: dict = field(default_factory=dict)
    source_ids: list[str] = field(default_factory=list)
    trust: int = 1

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "properties": self.properties,
            "source_ids": self.source_ids,
            "trust": self.trust,
        }
