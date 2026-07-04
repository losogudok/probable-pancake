"""Domain ontology for the mining-metallurgy scientific knowledge graph.

This module intentionally keeps ideas from core/ontology.py: simple, no YAML,
TOML, JSON config, or extra runtime dependencies.

The file contains two layers:

1. Legacy-compatible exports: EntityType, RelationType, SYNONYMS,
   MATERIAL_KEYWORDS, PROCESS_KEYWORDS, EQUIPMENT_KEYWORDS,
   PARAMETER_KEYWORDS, normalize_term(), Entity, Relation.

2. A small extensible ontology registry: DomainOntology, EntityTypeSpec,
   RelationTypeSpec, TermSpec, OntologyRegistry. New domain modules can later
   expose ONTOLOGY or ONTOLOGIES and be loaded with load_ontology_module().
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Any


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def enum_value(value: str | Enum) -> str:
    """Return the string value for either a plain string or a str Enum."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def normalize_key(value: str | Enum) -> str:
    """Case-insensitive key for ids, aliases, and enum/string values."""
    return enum_value(value).strip().lower()


# ---------------------------------------------------------------------------
# Entity types: built-in core values, not the whole possible ontology
# ---------------------------------------------------------------------------


class EntityType(str, Enum):
    # Evidence / RAG layer
    DOCUMENT = "Document"
    SOURCE_SPAN = "SourceSpan"
    CLAIM = "Claim"

    # Original mining-metallurgy core
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

    # Useful generic extensions
    MODEL = "Model"
    METRIC = "Metric"
    RISK = "Risk"
    ENGINEERING_SOLUTION = "EngineeringSolution"

    # Underground mining / geomechanics extension
    MINE_OBJECT = "MineObject"
    ROCK_MASS = "RockMass"
    GEOLOGICAL_FEATURE = "GeologicalFeature"


# ---------------------------------------------------------------------------
# Relationship types: built-in core values, not the whole possible ontology
# ---------------------------------------------------------------------------


class RelationType(str, Enum):
    # Evidence / RAG layer
    HAS_SPAN = "has_span"
    MENTIONS = "mentions"
    SUPPORTED_BY = "supported_by"
    ABOUT = "about"

    # Original domain relations
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

    # Common graph-analysis / engineering relations
    OPERATES_AT_CONDITION = "operates_at_condition"
    CONTAINS = "contains"
    MITIGATES = "mitigates"
    MODELS = "models"
    CALCULATES = "calculates"
    IN_ROCK_MASS = "in_rock_mass"
    INTERSECTS = "intersects"


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
    score = max(0, min(5, int(score)))
    return "★" * score + "☆" * (5 - score)


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
# Ontology registry model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityTypeSpec:
    """Schema-level description of an entity type.

    parent is intentionally a string, not an enum: domain modules may introduce
    types unknown to this file.
    """

    id: str
    label_ru: str = ""
    label_en: str = ""
    parent: str | None = None
    domain: str = "common"
    description: str = ""
    examples: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationTypeSpec:
    """Schema-level description of a relation type.

    source_types and target_types support "*" for deliberately generic links,
    for example Claim --about--> * or SourceSpan --mentions--> *.
    """

    id: str
    source_types: tuple[str, ...] = ("*",)
    target_types: tuple[str, ...] = ("*",)
    domain: str = "common"
    label_ru: str = ""
    label_en: str = ""
    inverse: str | None = None
    symmetric: bool = False
    description: str = ""


@dataclass(frozen=True)
class TermSpec:
    """A canonical term and its aliases.

    match is a hint for future extractors: exact_phrase, word_boundary,
    chemical_symbol, regex, context_required, etc. The current registry only
    stores it; matching policy remains in extractor code.
    """

    id: str
    type: str
    canonical: str
    aliases: tuple[str, ...] = ()
    domain: str = "common"
    canonical_en: str = ""
    parent_id: str | None = None
    match: str = "exact_phrase"
    properties: dict[str, Any] = field(default_factory=dict)

    def all_names(self) -> tuple[str, ...]:
        names = [self.canonical]
        if self.canonical_en:
            names.append(self.canonical_en)
        names.extend(self.aliases)
        # Keep order but remove exact duplicates.
        return tuple(dict.fromkeys(n for n in names if n))


@dataclass(frozen=True)
class DomainOntology:
    """A compact Python-defined ontology module."""

    domain: str
    version: str = "0.1"
    entity_types: tuple[EntityTypeSpec, ...] = ()
    relation_types: tuple[RelationTypeSpec, ...] = ()
    terms: tuple[TermSpec, ...] = ()


class OntologyRegistry:
    """Runtime registry for entity types, relations, terms, and aliases.

    It is intentionally small: no RDF/OWL semantics, only enough structure to
    drive extraction, relation validation, Neo4j writing, and RAG prompts.
    """

    def __init__(self) -> None:
        self.entity_types: dict[str, EntityTypeSpec] = {}
        self.relation_types: dict[str, list[RelationTypeSpec]] = {}
        self.terms: dict[str, TermSpec] = {}
        self.alias_to_term_ids: dict[str, list[str]] = {}
        self.alias_to_canonical: dict[str, str] = {}
        self.ontologies: dict[str, DomainOntology] = {}

    def register(self, ontology: DomainOntology) -> None:
        self.ontologies[ontology.domain] = ontology
        for spec in ontology.entity_types:
            self.register_entity_type(spec)
        for spec in ontology.relation_types:
            self.register_relation_type(spec)
        for term in ontology.terms:
            self.register_term(term)

    def register_entity_type(self, spec: EntityTypeSpec) -> None:
        key = normalize_key(spec.id)
        existing = self.entity_types.get(key)
        if existing is None or (existing.domain != "common" and spec.domain == "common"):
            self.entity_types[key] = spec

    def register_relation_type(self, spec: RelationTypeSpec) -> None:
        self.relation_types.setdefault(normalize_key(spec.id), []).append(spec)

    def register_term(self, term: TermSpec) -> None:
        self.terms[term.id] = term
        for alias in term.all_names():
            key = normalize_key(alias)
            self.alias_to_term_ids.setdefault(key, [])
            if term.id not in self.alias_to_term_ids[key]:
                self.alias_to_term_ids[key].append(term.id)
            # Legacy behavior: alias -> canonical string. Ambiguous aliases keep
            # the first registered canonical, while resolve_term() can disambiguate.
            self.alias_to_canonical.setdefault(key, term.canonical)

    def get_entity_type(self, type_id: str | EntityType) -> EntityTypeSpec | None:
        return self.entity_types.get(normalize_key(type_id))

    def get_relation_type(self, relation_id: str | RelationType) -> RelationTypeSpec | None:
        schemas = self.relation_types.get(normalize_key(relation_id), [])
        return schemas[0] if schemas else None

    def get_relation_schemas(self, relation_id: str | RelationType) -> list[RelationTypeSpec]:
        return list(self.relation_types.get(normalize_key(relation_id), []))

    def type_ids(self, domain: str | None = None) -> list[str]:
        specs = self.entity_types.values()
        if domain is not None:
            specs = (s for s in specs if s.domain == domain)
        return sorted({s.id for s in specs})

    def relation_ids(self, domain: str | None = None) -> list[str]:
        specs = (s for schemas in self.relation_types.values() for s in schemas)
        if domain is not None:
            specs = (s for s in specs if s.domain == domain)
        return sorted({s.id for s in specs})

    def resolve_term(
        self,
        term: str,
        *,
        domain: str | None = None,
        entity_type: str | EntityType | None = None,
    ) -> TermSpec | None:
        """Resolve an alias to a TermSpec, optionally constrained by domain/type."""
        candidates = [self.terms[term_id] for term_id in self.alias_to_term_ids.get(normalize_key(term), [])]
        if domain is not None:
            exact_domain = [t for t in candidates if t.domain == domain]
            if exact_domain:
                candidates = exact_domain
        if entity_type is not None:
            target_type = enum_value(entity_type)
            exact_type = [t for t in candidates if self.is_type_or_child(t.type, target_type)]
            if exact_type:
                candidates = exact_type
        return candidates[0] if candidates else None

    def normalize_term(
        self,
        term: str,
        *,
        domain: str | None = None,
        entity_type: str | EntityType | None = None,
    ) -> str:
        """Normalize alias to canonical form; returns original trimmed term on miss."""
        resolved = self.resolve_term(term, domain=domain, entity_type=entity_type)
        return resolved.canonical if resolved else term.strip()

    def canonical_id(
        self,
        term: str,
        *,
        domain: str | None = None,
        entity_type: str | EntityType | None = None,
    ) -> str | None:
        resolved = self.resolve_term(term, domain=domain, entity_type=entity_type)
        return resolved.id if resolved else None

    def is_type_or_child(self, type_id: str | EntityType, expected_type: str | EntityType) -> bool:
        """Return True if type_id equals expected_type or inherits from it."""
        current = enum_value(type_id)
        expected = enum_value(expected_type)
        if normalize_key(current) == normalize_key(expected):
            return True
        seen: set[str] = set()
        while current and normalize_key(current) not in seen:
            seen.add(normalize_key(current))
            spec = self.get_entity_type(current)
            if not spec or not spec.parent:
                return False
            current = spec.parent
            if normalize_key(current) == normalize_key(expected):
                return True
        return False

    def keywords_for_type(
        self,
        entity_type: str | EntityType,
        *,
        domains: Iterable[str] | None = None,
        include_children: bool = True,
    ) -> set[str]:
        """Return canonical terms and aliases for a type.

        include_children=True means keywords_for_type("Material") also includes
        terms typed as child classes such as Chemical or RockMass.
        """
        allowed_domains = set(domains) if domains is not None else None
        target_type = enum_value(entity_type)
        keywords: set[str] = set()
        for term in self.terms.values():
            if allowed_domains is not None and term.domain not in allowed_domains:
                continue
            if term.type == target_type or (include_children and self.is_type_or_child(term.type, target_type)):
                keywords.update(n.strip() for n in term.all_names() if n.strip())
        return keywords

    def is_relation_allowed(
        self,
        source_type: str | EntityType,
        relation_type: str | RelationType,
        target_type: str | EntityType,
    ) -> bool:
        schemas = self.get_relation_schemas(relation_type)
        if not schemas:
            return False
        src = enum_value(source_type)
        dst = enum_value(target_type)
        for spec in schemas:
            source_ok = "*" in spec.source_types or any(self.is_type_or_child(src, allowed) for allowed in spec.source_types)
            target_ok = "*" in spec.target_types or any(self.is_type_or_child(dst, allowed) for allowed in spec.target_types)
            if source_ok and target_ok:
                return True
        return False

    def synonyms_dict(self) -> dict[str, list[str]]:
        """Legacy canonical -> aliases dictionary."""
        result: dict[str, list[str]] = {}
        for term in self.terms.values():
            aliases = [a for a in term.all_names() if normalize_key(a) != normalize_key(term.canonical)]
            result.setdefault(term.canonical, [])
            for alias in aliases:
                if alias not in result[term.canonical]:
                    result[term.canonical].append(alias)
        return result

    def llm_schema(self, domains: Iterable[str] | None = None) -> dict[str, list[str]]:
        """Small schema fragment for prompts, not a full ontology dump."""
        allowed_domains = set(domains) if domains is not None else None

        def domain_ok(domain: str) -> bool:
            return allowed_domains is None or domain in allowed_domains or domain == "common"

        return {
            "entity_types": sorted({s.id for s in self.entity_types.values() if domain_ok(s.domain)}),
            "relation_types": sorted({
                s.id
                for schemas in self.relation_types.values()
                for s in schemas
                if domain_ok(s.domain)
            }),
        }


# ---------------------------------------------------------------------------
# Built-in ontology definitions
# ---------------------------------------------------------------------------


def E(id_: str, **kwargs: Any) -> EntityTypeSpec:
    return EntityTypeSpec(id=enum_value(id_), **kwargs)


def R(id_: str, source: Iterable[str | EntityType] = ("*",), target: Iterable[str | EntityType] = ("*",), **kwargs: Any) -> RelationTypeSpec:
    return RelationTypeSpec(
        id=enum_value(id_),
        source_types=tuple(enum_value(s) for s in source),
        target_types=tuple(enum_value(t) for t in target),
        **kwargs,
    )


def T(
    id_: str,
    type_: str | EntityType,
    canonical: str,
    aliases: Iterable[str] = (),
    **kwargs: Any,
) -> TermSpec:
    return TermSpec(id=id_, type=enum_value(type_), canonical=canonical, aliases=tuple(aliases), **kwargs)


COMMON_ONTOLOGY = DomainOntology(
    domain="common",
    version="0.1",
    entity_types=(
        E(EntityType.DOCUMENT, label_ru="Документ"),
        E(EntityType.SOURCE_SPAN, label_ru="Фрагмент источника"),
        E(EntityType.CLAIM, label_ru="Утверждение"),
        E(EntityType.MATERIAL, label_ru="Материал"),
        E(EntityType.PROCESS, label_ru="Процесс"),
        E(EntityType.EQUIPMENT, label_ru="Оборудование"),
        E(EntityType.FACILITY, label_ru="Объект / площадка"),
        E(EntityType.EXPERIMENT, label_ru="Эксперимент"),
        E(EntityType.PUBLICATION, label_ru="Публикация", parent=EntityType.DOCUMENT.value),
        E(EntityType.PATENT, label_ru="Патент", parent=EntityType.DOCUMENT.value),
        E(EntityType.PROPERTY, label_ru="Свойство"),
        E(EntityType.PARAMETER, label_ru="Параметр"),
        E(EntityType.CONDITION, label_ru="Условие"),
        E(EntityType.METRIC, label_ru="Показатель"),
        E(EntityType.RESULT, label_ru="Результат"),
        E(EntityType.EXPERT, label_ru="Эксперт"),
        E(EntityType.ORGANIZATION, label_ru="Организация"),
        E(EntityType.RECOMMENDATION, label_ru="Рекомендация"),
        E(EntityType.TECHNOLOGY, label_ru="Технология"),
        E(EntityType.METHOD, label_ru="Метод"),
        E(EntityType.CHEMICAL, label_ru="Химическое вещество", parent=EntityType.MATERIAL.value),
        E(EntityType.MODEL, label_ru="Модель"),
        E(EntityType.RISK, label_ru="Риск"),
        E(EntityType.ENGINEERING_SOLUTION, label_ru="Инженерное решение"),
    ),
    relation_types=(
        R(RelationType.HAS_SPAN, [EntityType.DOCUMENT], [EntityType.SOURCE_SPAN]),
        R(RelationType.MENTIONS, [EntityType.SOURCE_SPAN], ["*"]),
        R(RelationType.SUPPORTED_BY, [EntityType.CLAIM], [EntityType.SOURCE_SPAN, EntityType.DOCUMENT]),
        R(RelationType.ABOUT, [EntityType.CLAIM], ["*"]),
        R(RelationType.DESCRIBED_IN, ["*"], [EntityType.DOCUMENT, EntityType.SOURCE_SPAN]),
        R(RelationType.CITES, [EntityType.DOCUMENT, EntityType.PUBLICATION, EntityType.PATENT], [EntityType.DOCUMENT]),
        R(RelationType.DERIVED_FROM, ["*"], [EntityType.DOCUMENT, EntityType.SOURCE_SPAN, EntityType.CLAIM]),
        R(RelationType.CONTRADICTED_BY, [EntityType.CLAIM, EntityType.RESULT, EntityType.RECOMMENDATION], [EntityType.CLAIM, EntityType.RESULT, EntityType.DOCUMENT]),
        R(RelationType.VALIDATED_BY, [EntityType.CLAIM, EntityType.TECHNOLOGY, EntityType.METHOD, EntityType.ENGINEERING_SOLUTION], [EntityType.EXPERIMENT, EntityType.PUBLICATION, EntityType.DOCUMENT]),
        R(RelationType.HAS_PARAMETER, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY, EntityType.METHOD, EntityType.MODEL, EntityType.ENGINEERING_SOLUTION], [EntityType.PARAMETER]),
        R(RelationType.HAS_CONDITION, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY, EntityType.METHOD, EntityType.MODEL, EntityType.ENGINEERING_SOLUTION], [EntityType.CONDITION]),
        R(RelationType.OPERATES_AT_CONDITION, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY, EntityType.METHOD], [EntityType.CONDITION]),
        R(RelationType.HAS_RESULT, [EntityType.EXPERIMENT, EntityType.PROCESS, EntityType.MODEL], [EntityType.RESULT, EntityType.METRIC]),
        R(RelationType.MEASURED_BY, [EntityType.PROPERTY, EntityType.PARAMETER, EntityType.METRIC], [EntityType.METHOD, EntityType.EQUIPMENT, EntityType.EXPERIMENT]),
        R(RelationType.PERFORMED_AT, [EntityType.EXPERIMENT, EntityType.PROCESS], [EntityType.FACILITY, EntityType.ORGANIZATION]),
        R(RelationType.PERFORMED_BY, [EntityType.EXPERIMENT, EntityType.PROCESS], [EntityType.EXPERT, EntityType.ORGANIZATION]),
        R(RelationType.EXPERT_IN, [EntityType.EXPERT, EntityType.ORGANIZATION], ["*"]),
        R(RelationType.WORKS_AT, [EntityType.EXPERT], [EntityType.ORGANIZATION, EntityType.FACILITY]),
        R(RelationType.BELONGS_TO, ["*"], ["*"]),
        R(RelationType.ALTERNATIVE_TO, [EntityType.METHOD, EntityType.TECHNOLOGY, EntityType.ENGINEERING_SOLUTION], [EntityType.METHOD, EntityType.TECHNOLOGY, EntityType.ENGINEERING_SOLUTION]),
    ),
    terms=(
        T("condition:ColdClimate", EntityType.CONDITION, "холодный климат", ("cold climate", "arctic", "крайний север")),
    ),
)


METALLURGY_ONTOLOGY = DomainOntology(
    domain="metallurgy",
    version="0.1",
    entity_types=(),
    relation_types=(
        R(RelationType.USES_MATERIAL, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY], [EntityType.MATERIAL], domain="metallurgy"),
        R(RelationType.USES_REAGENT, [EntityType.PROCESS, EntityType.EXPERIMENT], [EntityType.CHEMICAL, EntityType.MATERIAL], domain="metallurgy"),
        R(RelationType.USES_EQUIPMENT, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY], [EntityType.EQUIPMENT], domain="metallurgy"),
        R(RelationType.USES_METHOD, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY], [EntityType.METHOD], domain="metallurgy"),
        R(RelationType.PRODUCES, [EntityType.PROCESS, EntityType.EXPERIMENT, EntityType.TECHNOLOGY], [EntityType.MATERIAL, EntityType.RESULT], domain="metallurgy"),
        R(RelationType.IMPROVES, [EntityType.METHOD, EntityType.TECHNOLOGY, EntityType.PROCESS], [EntityType.METRIC, EntityType.PROPERTY, EntityType.RESULT], domain="metallurgy"),
        R(RelationType.DECREASES, [EntityType.METHOD, EntityType.TECHNOLOGY, EntityType.PROCESS], [EntityType.METRIC, EntityType.PROPERTY, EntityType.RESULT], domain="metallurgy"),
        R(RelationType.REQUIRES, [EntityType.PROCESS, EntityType.TECHNOLOGY, EntityType.METHOD], [EntityType.EQUIPMENT, EntityType.MATERIAL, EntityType.CONDITION, EntityType.PARAMETER], domain="metallurgy"),
        R(RelationType.RECOMMENDED_FOR, [EntityType.RECOMMENDATION, EntityType.METHOD, EntityType.TECHNOLOGY], [EntityType.PROCESS, EntityType.MATERIAL, EntityType.FACILITY], domain="metallurgy"),
        R(RelationType.APPLIES_TO, [EntityType.METHOD, EntityType.TECHNOLOGY, EntityType.RECOMMENDATION], [EntityType.MATERIAL, EntityType.PROCESS, EntityType.FACILITY], domain="metallurgy"),
        R(RelationType.CONTAINS, [EntityType.MATERIAL], [EntityType.MATERIAL, EntityType.CHEMICAL], domain="metallurgy"),
    ),
    terms=(
        # Processes
        T("process:Electrowinning", EntityType.PROCESS, "электроэкстракция", ("electrowinning", "электролиз", "electroextraction"), domain="metallurgy"),
        T("process:Leaching", EntityType.PROCESS, "выщелачивание", ("leaching", "кучное выщелачивание", "heap leaching"), domain="metallurgy"),
        T("process:Flotation", EntityType.PROCESS, "флотация", ("flotation", "пенная флотация", "froth flotation"), domain="metallurgy"),
        T("process:Smelting", EntityType.PROCESS, "плавка", ("smelting", "печь взвешенной плавки", "flash smelting"), domain="metallurgy"),
        T("process:Roasting", EntityType.PROCESS, "обжиг", ("roasting", "calcination"), domain="metallurgy"),
        T("process:Beneficiation", EntityType.PROCESS, "обогащение", ("beneficiation", "mineral processing", "concentration"), domain="metallurgy", match="context_required"),
        T("process:Sorption", EntityType.PROCESS, "сорбция", ("sorption", "adsorption", "ионный обмен", "ion exchange"), domain="metallurgy"),
        T("process:SolventExtraction", EntityType.PROCESS, "экстракция", ("solvent extraction", "жидкостная экстракция"), domain="metallurgy"),
        T("process:Cementation", EntityType.PROCESS, "цементация", ("cementation", "осаждение"), domain="metallurgy"),
        T("process:Purification", EntityType.PROCESS, "очистка", ("purification", "treatment", "водоочистка"), domain="metallurgy"),
        T("process:Desalination", EntityType.PROCESS, "обессоливание", ("desalination", "demineralization", "опреснение"), domain="metallurgy"),
        T("process:Filtration", EntityType.PROCESS, "фильтрация", ("filtration", "сгущение", "thickening"), domain="metallurgy"),
        T("process:Drying", EntityType.PROCESS, "сушка", ("drying", "обезвоживание"), domain="metallurgy"),
        T("process:Grinding", EntityType.PROCESS, "измельчение", ("grinding", "crushing", "дробление"), domain="metallurgy"),
        T("process:Agglomeration", EntityType.PROCESS, "агломерация", ("agglomeration", "окомкование", "pelletizing"), domain="metallurgy"),
        T("process:Briquetting", EntityType.PROCESS, "брикетирование", ("briquetting",), domain="metallurgy"),
        T("process:Depletion", EntityType.PROCESS, "обеднение", ("depletion",), domain="metallurgy"),

        # Materials / metals
        T("material:Ni", EntityType.MATERIAL, "никель", ("nickel", "Ni"), domain="metallurgy", match="chemical_symbol"),
        T("material:Cu", EntityType.MATERIAL, "медь", ("copper", "Cu"), domain="metallurgy", match="chemical_symbol"),
        T("material:Co", EntityType.MATERIAL, "кобальт", ("cobalt", "Co"), domain="metallurgy", match="chemical_symbol"),
        T("material:Au", EntityType.MATERIAL, "золото", ("gold", "Au"), domain="metallurgy", match="chemical_symbol"),
        T("material:Ag", EntityType.MATERIAL, "серебро", ("silver", "Ag"), domain="metallurgy", match="chemical_symbol"),
        T("material:Pt", EntityType.MATERIAL, "платина", ("platinum", "Pt"), domain="metallurgy", match="chemical_symbol"),
        T("material:Pd", EntityType.MATERIAL, "палладий", ("palladium", "Pd"), domain="metallurgy", match="chemical_symbol"),
        T("material:Fe", EntityType.MATERIAL, "железо", ("iron", "Fe"), domain="metallurgy", match="chemical_symbol"),
        T("material:Zn", EntityType.MATERIAL, "цинк", ("zinc", "Zn"), domain="metallurgy", match="chemical_symbol"),
        T("material:Pb", EntityType.MATERIAL, "свинец", ("lead", "Pb"), domain="metallurgy", match="context_required"),
        T("material:Cr", EntityType.MATERIAL, "хром", ("chromium", "Cr"), domain="metallurgy", match="chemical_symbol"),
        T("material:Li", EntityType.MATERIAL, "литий", ("lithium", "Li"), domain="metallurgy", match="chemical_symbol"),

        # Materials / compounds / phases
        T("chemical:Sulfate", EntityType.CHEMICAL, "сульфат", ("sulfate", "сульфаты"), domain="metallurgy"),
        T("chemical:Chloride", EntityType.CHEMICAL, "хлорид", ("chloride", "хлориды"), domain="metallurgy"),
        T("chemical:Sulfide", EntityType.CHEMICAL, "сульфид", ("sulfide",), domain="metallurgy"),
        T("chemical:Oxide", EntityType.CHEMICAL, "оксид", ("oxide",), domain="metallurgy"),
        T("material:Gypsum", EntityType.MATERIAL, "гипс", ("gypsum", "техногенный гипс"), domain="metallurgy"),
        T("material:Catholyte", EntityType.MATERIAL, "католит", ("catholyte",), domain="metallurgy"),
        T("material:Anolyte", EntityType.MATERIAL, "анолит", ("anolyte",), domain="metallurgy"),
        T("material:Matte", EntityType.MATERIAL, "штейн", ("matte", "медный штейн", "никелевый штейн"), domain="metallurgy"),
        T("material:Slag", EntityType.MATERIAL, "шлак", ("slag",), domain="metallurgy"),
        T("material:Charge", EntityType.MATERIAL, "шихта", ("charge", "feed"), domain="metallurgy"),
        T("material:Concentrate", EntityType.MATERIAL, "концентрат", ("concentrate",), domain="metallurgy"),
        T("material:Ore", EntityType.MATERIAL, "руда", ("ore",), domain="metallurgy"),
        T("material:Tailings", EntityType.MATERIAL, "хвосты", ("tailings",), domain="metallurgy"),

        # Equipment
        T("equipment:ElectrowinningCell", EntityType.EQUIPMENT, "электролизная ванна", ("electrowinning cell", "электролизер", "ванна", "cell"), domain="metallurgy", match="context_required"),
        T("equipment:FlashSmeltingFurnace", EntityType.EQUIPMENT, "печь взвешенной плавки", ("flash smelting furnace", "ПВП", "печь", "furnace"), domain="metallurgy", match="context_required"),
        T("equipment:Converter", EntityType.EQUIPMENT, "конвертер", ("converter",), domain="metallurgy"),
        T("equipment:Mill", EntityType.EQUIPMENT, "мельница", ("mill", "grinding mill"), domain="metallurgy"),
        T("equipment:FlotationCell", EntityType.EQUIPMENT, "флотомашина", ("flotation cell", "флотационная машина"), domain="metallurgy"),
        T("equipment:Reactor", EntityType.EQUIPMENT, "реактор", ("reactor",), domain="metallurgy"),
        T("equipment:Diaphragm", EntityType.EQUIPMENT, "диафрагма", ("diaphragm",), domain="metallurgy"),
        T("equipment:Pump", EntityType.EQUIPMENT, "насос", ("pump",), domain="metallurgy"),

        # Reagents / environment
        T("chemical:Xanthate", EntityType.CHEMICAL, "ксантогенат", ("xanthate",), domain="metallurgy"),
        T("chemical:Cyanide", EntityType.CHEMICAL, "цианид", ("cyanide",), domain="metallurgy"),
        T("chemical:Lime", EntityType.CHEMICAL, "известь", ("lime", "CaO"), domain="metallurgy"),
        T("chemical:SulfuricAcid", EntityType.CHEMICAL, "серная кислота", ("sulfuric acid", "H2SO4"), domain="metallurgy"),
        T("material:MineWater", EntityType.MATERIAL, "шахтные воды", ("mine water", "mine drainage"), domain="metallurgy"),
        T("material:Wastewater", EntityType.MATERIAL, "сточные воды", ("wastewater", "effluent"), domain="metallurgy"),
        T("chemical:SO2", EntityType.CHEMICAL, "SO2", ("сернистый газ", "sulfur dioxide"), domain="metallurgy"),

        # Parameters / metrics
        T("parameter:Temperature", EntityType.PARAMETER, "температура", ("temperature",), domain="metallurgy"),
        T("parameter:FlowRate", EntityType.PARAMETER, "расход", ("flow rate", "скорость", "velocity", "speed"), domain="metallurgy"),
        T("parameter:Concentration", EntityType.PARAMETER, "концентрация", ("concentration",), domain="metallurgy", match="context_required"),
        T("parameter:Pressure", EntityType.PARAMETER, "давление", ("pressure",), domain="metallurgy"),
        T("parameter:Density", EntityType.PARAMETER, "плотность", ("density",), domain="metallurgy"),
        T("parameter:Voltage", EntityType.PARAMETER, "напряжение", ("voltage",), domain="metallurgy"),
        T("parameter:Current", EntityType.PARAMETER, "ток", ("current",), domain="metallurgy"),
        T("parameter:pH", EntityType.PARAMETER, "pH", ("ph",), domain="metallurgy"),
        T("metric:Capacity", EntityType.METRIC, "производительность", ("capacity",), domain="metallurgy"),
        T("metric:Recovery", EntityType.METRIC, "извлечение", ("recovery", "выход", "степень", "efficiency", "КПД"), domain="metallurgy"),
    ),
)


UNDERGROUND_MINING_ONTOLOGY = DomainOntology(
    domain="underground_mining",
    version="0.1",
    entity_types=(
        E(EntityType.MINE_OBJECT, label_ru="Объект подземных горных работ", parent=EntityType.FACILITY.value, domain="underground_mining"),
        E(EntityType.ROCK_MASS, label_ru="Горный массив", parent=EntityType.MATERIAL.value, domain="underground_mining"),
        E(EntityType.GEOLOGICAL_FEATURE, label_ru="Геологическая структура", domain="underground_mining"),
        E(EntityType.MODEL, label_ru="Цифровая / расчётная модель", domain="underground_mining"),
        E(EntityType.ENGINEERING_SOLUTION, label_ru="Инженерное решение", parent=EntityType.TECHNOLOGY.value, domain="underground_mining"),
        E(EntityType.RISK, label_ru="Горный риск", domain="underground_mining"),
        E(EntityType.METRIC, label_ru="Показатель проектного решения", domain="underground_mining"),
    ),
    relation_types=(
        R(RelationType.IN_ROCK_MASS, [EntityType.MINE_OBJECT], [EntityType.ROCK_MASS], domain="underground_mining"),
        R(RelationType.INTERSECTS, [EntityType.MINE_OBJECT], [EntityType.GEOLOGICAL_FEATURE], domain="underground_mining"),
        R(RelationType.APPLIES_TO, [EntityType.ENGINEERING_SOLUTION, EntityType.METHOD, EntityType.TECHNOLOGY], [EntityType.MINE_OBJECT, EntityType.ROCK_MASS, EntityType.FACILITY], domain="underground_mining"),
        R(RelationType.MITIGATES, [EntityType.ENGINEERING_SOLUTION, EntityType.METHOD, EntityType.TECHNOLOGY], [EntityType.RISK], domain="underground_mining"),
        R(RelationType.MODELS, [EntityType.MODEL], [EntityType.MINE_OBJECT, EntityType.ROCK_MASS, EntityType.GEOLOGICAL_FEATURE, EntityType.PROCESS], domain="underground_mining"),
        R(RelationType.CALCULATES, [EntityType.MODEL], [EntityType.METRIC, EntityType.PARAMETER, EntityType.PROPERTY], domain="underground_mining"),
        R(RelationType.IMPROVES, [EntityType.ENGINEERING_SOLUTION, EntityType.METHOD, EntityType.TECHNOLOGY], [EntityType.METRIC], domain="underground_mining"),
        R(RelationType.DECREASES, [EntityType.ENGINEERING_SOLUTION, EntityType.METHOD, EntityType.TECHNOLOGY], [EntityType.RISK, EntityType.METRIC], domain="underground_mining"),
        R(RelationType.USES_EQUIPMENT, [EntityType.PROCESS, EntityType.ENGINEERING_SOLUTION], [EntityType.EQUIPMENT], domain="underground_mining"),
    ),
    terms=(
        # Mine objects
        T("underground:OrePass", EntityType.MINE_OBJECT, "рудоспуск", ("ore pass", "капитальный рудоспуск"), domain="underground_mining"),
        T("underground:Drift", EntityType.MINE_OBJECT, "штрек", ("drift",), domain="underground_mining"),
        T("underground:Crosscut", EntityType.MINE_OBJECT, "квершлаг", ("crosscut",), domain="underground_mining"),
        T("underground:Stope", EntityType.MINE_OBJECT, "камера", ("stope", "очистная камера"), domain="underground_mining", match="context_required"),
        T("underground:Level", EntityType.MINE_OBJECT, "горизонт", ("level", "mine level"), domain="underground_mining", match="context_required"),
        T("underground:Shaft", EntityType.MINE_OBJECT, "ствол", ("shaft",), domain="underground_mining", match="context_required"),

        # Rock mass / geology
        T("underground:RockMass", EntityType.ROCK_MASS, "горный массив", ("rock mass", "массив горных пород"), domain="underground_mining"),
        T("underground:DisturbedRockMass", EntityType.ROCK_MASS, "нарушенный массив", ("disturbed rock mass", "трещиноватый массив"), domain="underground_mining"),
        T("underground:RockburstHazardousRockMass", EntityType.ROCK_MASS, "удароопасный массив", ("rockburst-prone rock mass", "burst-prone rock mass"), domain="underground_mining"),
        T("underground:OreBody", EntityType.GEOLOGICAL_FEATURE, "рудное тело", ("ore body", "orebody"), domain="underground_mining"),
        T("underground:Fault", EntityType.GEOLOGICAL_FEATURE, "разлом", ("fault",), domain="underground_mining"),
        T("underground:Fracturing", EntityType.GEOLOGICAL_FEATURE, "трещиноватость", ("fracturing", "jointing"), domain="underground_mining"),

        # Models
        T("underground:RockMassModel", EntityType.MODEL, "модель горного массива", ("rock mass model", "RockMassModel"), domain="underground_mining", properties={"model_type": "rock_mass"}),
        T("underground:GeomechanicalModel", EntityType.MODEL, "геомеханическая модель", ("geomechanical model", "GeomechanicalModel"), domain="underground_mining", properties={"model_type": "geomechanical"}),
        T("underground:StressStrainModel", EntityType.MODEL, "модель НДС", ("stress-strain model", "модель напряжённо-деформированного состояния", "NDS model"), domain="underground_mining", properties={"model_type": "stress_strain"}),
        T("underground:MineDesignModel", EntityType.MODEL, "проектная модель ПГР", ("mine design model", "модель подземных горных работ"), domain="underground_mining", properties={"model_type": "mine_design"}),
        T("underground:BIMModel", EntityType.MODEL, "BIM-модель", ("BIM model", "информационная модель"), domain="underground_mining", properties={"model_type": "bim"}),

        # Engineering solutions / processes / equipment
        T("underground:Support", EntityType.PROCESS, "крепление", ("support", "ground support"), domain="underground_mining"),
        T("underground:Excavation", EntityType.PROCESS, "проходка", ("excavation", "development"), domain="underground_mining"),
        T("underground:Stoping", EntityType.PROCESS, "выемка", ("stoping", "mining"), domain="underground_mining"),
        T("underground:Backfilling", EntityType.PROCESS, "закладка", ("backfilling",), domain="underground_mining"),
        T("underground:Ventilation", EntityType.PROCESS, "вентиляция", ("ventilation",), domain="underground_mining"),
        T("underground:CombinedSupport", EntityType.ENGINEERING_SOLUTION, "комбинированная крепь", ("combined support", "усиленная комбинированная крепь"), domain="underground_mining"),
        T("underground:RockBolting", EntityType.ENGINEERING_SOLUTION, "анкерное крепление", ("rock bolting", "анкер", "СЗБА"), domain="underground_mining"),
        T("underground:Shotcrete", EntityType.ENGINEERING_SOLUTION, "набрызгбетон", ("shotcrete", "sprayed concrete"), domain="underground_mining"),
        T("underground:MonitoringSystem", EntityType.EQUIPMENT, "система мониторинга", ("monitoring system", "геомеханический мониторинг"), domain="underground_mining"),

        # Risks / metrics / parameters
        T("underground:CollapseRisk", EntityType.RISK, "обрушение", ("collapse", "caving", "обрушение стенок"), domain="underground_mining"),
        T("underground:RockburstRisk", EntityType.RISK, "горный удар", ("rockburst", "rock burst"), domain="underground_mining"),
        T("underground:WaterInflowRisk", EntityType.RISK, "водоприток", ("water inflow",), domain="underground_mining"),
        T("underground:Stability", EntityType.METRIC, "устойчивость", ("stability",), domain="underground_mining"),
        T("underground:StressStrainState", EntityType.METRIC, "НДС", ("напряжённо-деформированное состояние", "stress-strain state"), domain="underground_mining"),
        T("underground:Displacement", EntityType.METRIC, "смещение", ("displacement", "деформация"), domain="underground_mining"),
        T("underground:Depth", EntityType.PARAMETER, "глубина", ("depth",), domain="underground_mining"),
        T("underground:RMR", EntityType.PARAMETER, "RMR", ("rock mass rating",), domain="underground_mining"),
        T("underground:QSystem", EntityType.PARAMETER, "Q", ("Q-system", "Q system"), domain="underground_mining"),
        T("underground:UCS", EntityType.PARAMETER, "прочность на одноосное сжатие", ("UCS", "uniaxial compressive strength"), domain="underground_mining"),
        T("underground:Stress", EntityType.PARAMETER, "напряжение", ("stress", "горное давление"), domain="underground_mining"),
    ),
)


# ---------------------------------------------------------------------------
# Registry creation and optional runtime module loading
# ---------------------------------------------------------------------------


def build_default_registry() -> OntologyRegistry:
    registry = OntologyRegistry()
    registry.register(COMMON_ONTOLOGY)
    registry.register(METALLURGY_ONTOLOGY)
    registry.register(UNDERGROUND_MINING_ONTOLOGY)
    return registry


DEFAULT_REGISTRY = build_default_registry()


def load_ontology_module(
    module_name: str,
    *,
    registry: OntologyRegistry | None = None,
    reload_module: bool = False,
) -> OntologyRegistry:
    """Load a Python ontology extension module into a registry.

    The module may expose either:
      - ONTOLOGY: DomainOntology
      - ONTOLOGIES: iterable[DomainOntology]

    Example future module:

        from app.core.ontology import DomainOntology, T, E, R
        ONTOLOGY = DomainOntology(domain="rare_earths", terms=(...))
    """
    target = registry or DEFAULT_REGISTRY
    module = importlib.import_module(module_name)
    if reload_module:
        module = importlib.reload(module)

    if hasattr(module, "ONTOLOGY"):
        target.register(module.ONTOLOGY)
    if hasattr(module, "ONTOLOGIES"):
        for ontology in module.ONTOLOGIES:
            target.register(ontology)
    if not hasattr(module, "ONTOLOGY") and not hasattr(module, "ONTOLOGIES"):
        raise AttributeError(f"{module_name!r} must define ONTOLOGY or ONTOLOGIES")
    return target


# ---------------------------------------------------------------------------
# Legacy-compatible synonym dictionary and keyword sets
# ---------------------------------------------------------------------------


SYNONYMS: dict[str, list[str]] = DEFAULT_REGISTRY.synonyms_dict()
ALIAS_TO_CANONICAL: dict[str, str] = dict(DEFAULT_REGISTRY.alias_to_canonical)


def normalize_term(term: str) -> str:
    """Normalize a term to its canonical form using the default registry."""
    return DEFAULT_REGISTRY.normalize_term(term)


MATERIAL_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.MATERIAL)
PROCESS_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.PROCESS)
EQUIPMENT_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.EQUIPMENT)
PARAMETER_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.PARAMETER)

# Optional domain-specific keyword exports for new extractors.
MINE_OBJECT_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.MINE_OBJECT)
ROCK_MASS_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.ROCK_MASS)
MODEL_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.MODEL)
RISK_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.RISK)
METRIC_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.METRIC)
ENGINEERING_SOLUTION_KEYWORDS = DEFAULT_REGISTRY.keywords_for_type(EntityType.ENGINEERING_SOLUTION)

UNIT_PATTERNS = {
    "мг/л", "mg/l", "мг/дм³", "г/л", "g/l", "%", "°c", "°с", "м/с", "m/s",
    "л/мин", "l/min", "м³/ч", "m³/h", "т/сут", "t/day", "bar", "атм",
    "в", "v", "а", "a", "ка", "ka", "мс", "ms", "с", "мин", "ч",
    "руб/м³", "руб/т", "$/t", "usd/t", "моль/л", "mol/l",
    # Useful for underground mining / geomechanics
    "м", "m", "мм", "mm", "мпа", "mpa", "гпа", "gpa", "кн", "kn",
    "м³", "m³", "т", "t", "т/м³", "t/m³",
}


# ---------------------------------------------------------------------------
# Graph payload dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """A node in the knowledge graph.

    type accepts either the legacy EntityType enum or a new runtime string type
    registered in OntologyRegistry.
    """

    id: str
    type: str | EntityType
    name: str
    canonical: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    source_ids: list[str] = field(default_factory=list)
    trust: int = 1
    geography: Geography | str = Geography.UNKNOWN
    domain: str = "common"
    ontology_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": enum_value(self.type),
            "name": self.name,
            "canonical": self.canonical or self.name,
            "properties": self.properties,
            "source_ids": self.source_ids,
            "trust": self.trust,
            "geography": enum_value(self.geography),
            "domain": self.domain,
            "ontology_version": self.ontology_version,
        }


@dataclass
class Relation:
    """An edge in the knowledge graph.

    type accepts either the legacy RelationType enum or a new runtime string type
    registered in OntologyRegistry.
    """

    source: str
    target: str
    type: str | RelationType
    properties: dict[str, Any] = field(default_factory=dict)
    source_ids: list[str] = field(default_factory=list)
    trust: int = 1
    domain: str = "common"
    ontology_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": enum_value(self.type),
            "properties": self.properties,
            "source_ids": self.source_ids,
            "trust": self.trust,
            "domain": self.domain,
            "ontology_version": self.ontology_version,
        }
