"""Knowledge Graph built on networkx with persistence.

Stores entities as nodes and relations as edges, with provenance tracking
(source document IDs), trust scores, and support for graph queries.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Any
from collections import defaultdict

import networkx as nx

from ..core.config import GRAPH_PATH
from ..core.ontology import (
    EntityType, RelationType, Entity, Relation,
    SourceType, TRUST_SCORES, Geography, normalize_term,
)
from ..core.models import Document, Chunk

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Knowledge graph with entities, relations, provenance, and trust."""

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        # Index: (type, canonical) -> node_id
        self._entity_index: dict[tuple[str, str], str] = {}

    def _make_node_id(self, entity_type: str, canonical: str) -> str:
        return f"{entity_type}:{canonical}"

    def add_entity(
        self,
        entity_type: str,
        name: str,
        canonical: Optional[str] = None,
        source_id: Optional[str] = None,
        trust: int = 1,
        geography: str = "Unknown",
        properties: Optional[dict] = None,
    ) -> str:
        """Add or update an entity node. Returns the node ID."""
        canonical = canonical or normalize_term(name)
        node_id = self._make_node_id(entity_type, canonical)

        if node_id in self.graph:
            # Update existing node
            node = self.graph.nodes[node_id]
            node["source_ids"] = list(set(node.get("source_ids", []) + ([source_id] if source_id else [])))
            node["trust"] = max(node.get("trust", 1), trust)
            if properties:
                node["properties"].update(properties)
            # Track all names seen
            names = set(node.get("names", []))
            names.add(name)
            node["names"] = sorted(names)
        else:
            self.graph.add_node(
                node_id,
                type=entity_type,
                name=name,
                canonical=canonical,
                names=[name],
                source_ids=[source_id] if source_id else [],
                trust=trust,
                geography=geography,
                properties=properties or {},
            )
            self._entity_index[(entity_type, canonical)] = node_id

        return node_id

    def add_relation(
        self,
        source_canonical: str,
        source_type: str,
        target_canonical: str,
        target_type: str,
        relation_type: str,
        source_id: Optional[str] = None,
        trust: int = 1,
        properties: Optional[dict] = None,
    ) -> None:
        """Add a relation edge between two entities."""
        source_id_node = self._make_node_id(source_type, source_canonical)
        target_id_node = self._make_node_id(target_type, target_canonical)

        # Ensure nodes exist
        if source_id_node not in self.graph:
            self.add_entity(source_type, source_canonical, source_canonical)
        if target_id_node not in self.graph:
            self.add_entity(target_type, target_canonical, target_canonical)

        # Check if edge already exists (MultiDiGraph allows parallel edges)
        # We merge edges with same source/target/type
        for u, v, key, data in self.graph.edges(source_id_node, data=True, keys=True):
            if v == target_id_node and data.get("type") == relation_type:
                # Merge: add source_id, update trust
                data["source_ids"] = list(set(
                    data.get("source_ids", []) + ([source_id] if source_id else [])))
                data["trust"] = max(data.get("trust", 1), trust)
                if properties:
                    data["properties"].update(properties)
                return

        self.graph.add_edge(
            source_id_node,
            target_id_node,
            type=relation_type,
            source_ids=[source_id] if source_id else [],
            trust=trust,
            properties=properties or {},
        )

    def add_document(self, doc: Document) -> None:
        """Add a document as a Publication node and link its entities."""
        pub_id = self.add_entity(
            EntityType.PUBLICATION.value,
            doc.title or doc.filename,
            canonical=f"doc:{doc.id}",
            source_id=doc.id,
            trust=doc.trust,
            geography=doc.geography,
            properties={
                "filename": doc.filename,
                "category": doc.category,
                "source_type": doc.source_type,
                "year": doc.year,
                "language": doc.language,
                "authors": doc.authors,
                "num_pages": doc.num_pages,
                "num_chunks": doc.num_chunks,
            },
        )

        # Add authors as Expert entities
        for author in doc.authors:
            expert_id = self.add_entity(
                EntityType.EXPERT.value,
                author,
                canonical=author,
                source_id=doc.id,
                trust=doc.trust,
            )
            self.add_relation(
                author, EntityType.EXPERT.value,
                f"doc:{doc.id}", EntityType.PUBLICATION.value,
                RelationType.DESCRIBED_IN.value,
                source_id=doc.id, trust=doc.trust,
            )

    def add_extraction(
        self,
        doc: Document,
        chunk: Chunk,
        extraction: dict,
    ) -> None:
        """Add extracted entities and relations from a chunk to the graph."""
        doc_id = doc.id

        # Add entities
        entity_node_ids = []
        for ent in extraction.get("entities", []):
            node_id = self.add_entity(
                ent["type"],
                ent["name"],
                canonical=ent.get("canonical"),
                source_id=doc_id,
                trust=doc.trust,
                geography=doc.geography,
                properties={
                    "value": ent.get("value"),
                    "unit": ent.get("unit"),
                } if "value" in ent else {},
            )
            entity_node_ids.append((ent, node_id))

        # Add relations
        for rel in extraction.get("relations", []):
            source_type = rel.get("source_type", "")
            target_type = rel.get("target_type", "")

            # Try to infer types from entity list if not provided
            if not source_type or not target_type:
                ent_map = {e["canonical"]: e["type"] for e in extraction.get("entities", [])}
                if not source_type:
                    source_type = ent_map.get(rel["source"], EntityType.PROCESS.value)
                if not target_type:
                    target_type = ent_map.get(rel["target"], EntityType.MATERIAL.value)

            self.add_relation(
                rel["source"], source_type,
                rel["target"], target_type,
                rel["type"],
                source_id=doc_id,
                trust=doc.trust,
                properties={
                    "value": rel.get("value"),
                    "unit": rel.get("unit"),
                    "evidence": rel.get("evidence", ""),
                },
            )

        # Link entities to the document
        for ent, node_id in entity_node_ids:
            self.add_relation(
                ent.get("canonical", ent["name"]), ent["type"],
                f"doc:{doc.id}", EntityType.PUBLICATION.value,
                RelationType.DESCRIBED_IN.value,
                source_id=doc_id, trust=doc.trust,
            )

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_entity(self, node_id: str) -> Optional[dict]:
        """Get entity by node ID."""
        if node_id not in self.graph:
            return None
        return dict(self.graph.nodes[node_id])

    def find_entities(
        self,
        entity_type: Optional[str] = None,
        name: Optional[str] = None,
        canonical: Optional[str] = None,
    ) -> list[dict]:
        """Find entities by type and/or name."""
        results = []
        for node_id, data in self.graph.nodes(data=True):
            if entity_type and data.get("type") != entity_type:
                continue
            if canonical and data.get("canonical") != canonical:
                continue
            if name:
                name_lower = name.lower()
                if (name_lower not in data.get("name", "").lower() and
                    name_lower not in data.get("canonical", "").lower() and
                    not any(name_lower in n.lower() for n in data.get("names", []))):
                    continue
            results.append({"id": node_id, **data})
        return results

    def get_neighbors(
        self, node_id: str, max_depth: int = 2, limit: int = 50
    ) -> dict:
        """Get subgraph around a node (BFS traversal)."""
        if node_id not in self.graph:
            return {"nodes": [], "edges": []}

        nodes_set = {node_id}
        edges = []
        frontier = [node_id]

        for depth in range(max_depth):
            next_frontier = []
            for node in frontier:
                for _, target, key, data in self.graph.edges(node, data=True, keys=True):
                    if len(nodes_set) >= limit:
                        break
                    if target not in nodes_set:
                        nodes_set.add(target)
                        next_frontier.append(target)
                    edges.append({
                        "source": node, "target": target,
                        "type": data.get("type"), "trust": data.get("trust", 1),
                    })
                # Also check incoming edges
                for source, _, key, data in self.graph.in_edges(node, data=True, keys=True):
                    if len(nodes_set) >= limit:
                        break
                    if source not in nodes_set:
                        nodes_set.add(source)
                        next_frontier.append(source)
                    edges.append({
                        "source": source, "target": node,
                        "type": data.get("type"), "trust": data.get("trust", 1),
                    })
            frontier = next_frontier
            if not frontier:
                break

        nodes = []
        for nid in nodes_set:
            node_data = dict(self.graph.nodes[nid])
            node_data["id"] = nid
            nodes.append(node_data)

        return {"nodes": nodes, "edges": edges}

    def get_entity_by_type_and_name(
        self, entity_type: str, name: str
    ) -> Optional[str]:
        """Get node ID by type and canonical name."""
        canonical = normalize_term(name)
        return self._entity_index.get((entity_type, canonical))

    def get_process_material_chain(
        self, process_name: str, material_name: Optional[str] = None
    ) -> list[dict]:
        """Find chain: process -> material -> equipment -> parameters."""
        results = []
        proc_node = self.get_entity_by_type_and_name(
            EntityType.PROCESS.value, process_name)
        if not proc_node:
            return results

        for _, target, data in self.graph.edges(proc_node, data=True):
            target_data = self.graph.nodes[target]
            if material_name and material_name.lower() not in target_data.get("canonical", "").lower():
                continue
            results.append({
                "process": process_name,
                "target": target_data.get("canonical"),
                "target_type": target_data.get("type"),
                "relation": data.get("type"),
                "value": data.get("properties", {}).get("value"),
                "unit": data.get("properties", {}).get("unit"),
                "trust": data.get("trust", 1),
                "source_ids": data.get("source_ids", []),
            })
        return results

    def find_contradictions(self) -> list[dict]:
        """Find entities with contradicting parameter values across sources."""
        contradictions = []

        # Group parameter edges by (process, parameter) and check for conflicting values
        param_edges = defaultdict(list)
        for u, v, data in self.graph.edges(data=True):
            if data.get("type") == RelationType.HAS_PARAMETER.value:
                proc = self.graph.nodes[u].get("canonical")
                param = self.graph.nodes[v].get("canonical")
                value = data.get("properties", {}).get("value")
                if value is not None:
                    param_edges[(proc, param)].append({
                        "value": value,
                        "unit": data.get("properties", {}).get("unit"),
                        "source_ids": data.get("source_ids", []),
                        "trust": data.get("trust", 1),
                    })

        for (proc, param), entries in param_edges.items():
            if len(entries) < 2:
                continue
            # Check for conflicting numeric values
            values = []
            for e in entries:
                v = e["value"]
                if isinstance(v, list):
                    values.append(v[0])
                elif isinstance(v, (int, float)):
                    values.append(v)

            if len(values) >= 2:
                vmin, vmax = min(values), max(values)
                if vmax > 0 and (vmax - vmin) / vmax > 0.3:  # >30% difference
                    contradictions.append({
                        "process": proc,
                        "parameter": param,
                        "entries": entries,
                        "range": [vmin, vmax],
                    })

        return contradictions

    def find_gaps(self) -> list[dict]:
        """Find combinations of process + material that have no experiments."""
        gaps = []

        # Get all processes and materials
        processes = [n for n, d in self.graph.nodes(data=True)
                     if d.get("type") == EntityType.PROCESS.value]
        materials = [n for n, d in self.graph.nodes(data=True)
                     if d.get("type") == EntityType.MATERIAL.value]

        # Find which process-material pairs have relations
        existing_pairs = set()
        for u, v, data in self.graph.edges(data=True):
            if data.get("type") == RelationType.USES_MATERIAL.value:
                existing_pairs.add((u, v))

        # Report missing pairs for top processes/materials
        for proc in processes[:20]:
            for mat in materials[:20]:
                if (proc, mat) not in existing_pairs:
                    proc_data = self.graph.nodes[proc]
                    mat_data = self.graph.nodes[mat]
                    # Only report if both have multiple sources (are "important")
                    if (len(proc_data.get("source_ids", [])) >= 2 and
                        len(mat_data.get("source_ids", [])) >= 2):
                        gaps.append({
                            "process": proc_data.get("canonical"),
                            "material": mat_data.get("canonical"),
                            "process_sources": len(proc_data.get("source_ids", [])),
                            "material_sources": len(mat_data.get("source_ids", [])),
                        })

        return gaps[:50]

    def get_stats(self) -> dict:
        """Get graph statistics."""
        type_counts = defaultdict(int)
        for _, data in self.graph.nodes(data=True):
            type_counts[data.get("type", "Unknown")] += 1

        rel_counts = defaultdict(int)
        for _, _, data in self.graph.edges(data=True):
            rel_counts[data.get("type", "Unknown")] += 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "nodes_by_type": dict(type_counts),
            "edges_by_type": dict(rel_counts),
            "total_sources": len({n for n, d in self.graph.nodes(data=True)
                                  if d.get("type") == EntityType.PUBLICATION.value}),
        }

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def save(self, path: Optional[Path] = None) -> None:
        """Save graph to JSON."""
        path = path or GRAPH_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        data = nx.node_link_data(self.graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved knowledge graph: {self.graph.number_of_nodes()} nodes, "
                     f"{self.graph.number_of_edges()} edges -> {path}")

    def load(self, path: Optional[Path] = None) -> bool:
        """Load graph from JSON."""
        path = path or GRAPH_PATH
        if not path.exists():
            return False

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data, directed=True, multigraph=True)

        # Rebuild index
        self._entity_index = {}
        for node_id, node_data in self.graph.nodes(data=True):
            t = node_data.get("type", "")
            c = node_data.get("canonical", "")
            if t and c:
                self._entity_index[(t, c)] = node_id

        logger.info(f"Loaded knowledge graph: {self.graph.number_of_nodes()} nodes, "
                     f"{self.graph.number_of_edges()} edges")
        return True
