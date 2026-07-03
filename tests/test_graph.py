"""Tests for Knowledge Graph."""

import tempfile
from pathlib import Path
import networkx as nx
from app.graph.kg import KnowledgeGraph
from app.core.ontology import RelationType


def test_graph_creation():
    kg = KnowledgeGraph()
    assert kg.graph is not None
    assert len(kg.graph.nodes) == 0


def test_add_entity():
    kg = KnowledgeGraph()
    eid = kg.add_entity("Material", "никель", source_id="doc1")
    assert eid == "Material:никель"
    assert len(kg.graph.nodes) == 1


def test_add_relation():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "руда", source_id="doc1")
    kg.add_entity("Process", "обогащение", source_id="doc1")
    kg.add_relation("руда", "Material", "обогащение", "Process",
                    "undergoes", source_id="doc1")
    assert len(kg.graph.edges) == 1


def test_add_entity_twice():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "никель", source_id="doc1")
    kg.add_entity("Material", "nickel", source_id="doc2")
    assert len(kg.graph.nodes) == 1


def test_neighbors():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "руда", source_id="doc1")
    kg.add_entity("Process", "обогащение", source_id="doc1")
    kg.add_entity("Equipment", "флотомашина", source_id="doc1")
    kg.add_relation("руда", "Material", "обогащение", "Process",
                    "undergoes", source_id="doc1")
    kg.add_relation("обогащение", "Process", "флотомашина", "Equipment",
                    "uses_equipment", source_id="doc1")
    neighbors = kg.get_neighbors("Process:обогащение", max_depth=1)
    assert len(neighbors) > 0


def test_process_material_chain():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "руда", source_id="doc1")
    kg.add_entity("Process", "обогащение", source_id="doc1")
    kg.add_entity("Material", "концентрат", source_id="doc1")
    kg.add_relation("руда", "Material", "обогащение", "Process",
                    "undergoes", source_id="doc1")
    kg.add_relation("обогащение", "Process", "концентрат", "Material",
                    "produces", source_id="doc1")
    chains = kg.get_process_material_chain("обогащение")
    assert len(chains) > 0


def test_contradictions():
    kg = KnowledgeGraph()
    kg.add_entity("Process", "плавка", source_id="doc1")
    kg.add_entity("Parameter", "parameter_температура", source_id="doc1")
    kg.graph.add_edge(
        "Process:плавка", "Parameter:parameter_температура",
        type=RelationType.HAS_PARAMETER.value,
        source_ids=["doc1"], trust=4,
        properties={"value": 1200, "unit": "°C"}
    )
    kg.graph.add_edge(
        "Process:плавка", "Parameter:parameter_температура",
        type=RelationType.HAS_PARAMETER.value,
        source_ids=["doc2"], trust=4,
        properties={"value": 700, "unit": "°C"}
    )
    contradictions = kg.find_contradictions()
    assert len(contradictions) > 0


def test_gaps():
    kg = KnowledgeGraph()
    # Add processes and materials with source_ids to count as sources
    kg.add_entity("Process", "обжиг", source_id="doc1")
    kg.add_entity("Process", "обжиг", source_id="doc2")
    kg.add_entity("Material", "никель", source_id="doc3")
    kg.add_entity("Material", "никель", source_id="doc4")
    gaps = kg.find_gaps()
    assert len(gaps) > 0


def test_persistence():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "никель", source_id="doc1")
    kg.add_entity("Process", "обогащение", source_id="doc1")
    kg.add_relation("никель", "Material", "обогащение", "Process",
                    "undergoes", source_id="doc1")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        fname = f.name
    kg.save(Path(fname))
    kg2 = KnowledgeGraph()
    kg2.load(Path(fname))
    assert len(kg2.graph.nodes) == len(kg.graph.nodes)
    assert len(kg2.graph.edges) == len(kg.graph.edges)
    Path(fname).unlink()


def test_stats():
    kg = KnowledgeGraph()
    kg.add_entity("Material", "никель", source_id="doc1")
    kg.add_entity("Process", "обогащение", source_id="doc1")
    stats = kg.get_stats()
    assert "total_nodes" in stats
    assert stats["total_nodes"] == 2
