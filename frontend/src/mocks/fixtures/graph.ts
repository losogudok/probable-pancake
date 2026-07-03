import type { KnowledgeSubgraph } from "../../domain/types";

export const knowledgeGraph: KnowledgeSubgraph = {
  nodes: [
    { id: "process-ew", type: "Process", label: "Электроэкстракция", canonical: "электроэкстракция", aliases: ["electrowinning"], sourceCount: 84, confidence: 96 },
    { id: "material-ni", type: "Material", label: "Никель", canonical: "никель", aliases: ["Ni", "nickel"], sourceCount: 312, confidence: 99 },
    { id: "material-catholyte", type: "Material", label: "Католит", canonical: "католит", aliases: ["catholyte"], sourceCount: 28, confidence: 94 },
    { id: "equipment-cell", type: "Equipment", label: "Электролизная ванна", canonical: "электролизная ванна", sourceCount: 41, confidence: 91 },
    { id: "parameter-flow", type: "Parameter", label: "Скорость циркуляции", canonical: "скорость циркуляции", sourceCount: 17, confidence: 88 },
    { id: "technology-loop", type: "Technology", label: "Малый контур", canonical: "малый контур циркуляции", sourceCount: 5, confidence: 82 },
    { id: "publication-review", type: "Publication", label: "Обзор 2025", canonical: "обзор электролитического производства", sourceCount: 1, confidence: 96 },
    { id: "expert-evgrafova", type: "Expert", label: "Евграфова А. К.", canonical: "Евграфова А. К.", sourceCount: 4, confidence: 90 },
    { id: "process-smelting", type: "Process", label: "Плавка", canonical: "плавка", sourceCount: 155, confidence: 98 },
    { id: "phase-matte", type: "Phase", label: "Штейн", canonical: "штейн", aliases: ["matte"], sourceCount: 96, confidence: 97 },
    { id: "phase-slag", type: "Phase", label: "Шлак", canonical: "шлак", aliases: ["slag"], sourceCount: 128, confidence: 98 },
  ],
  edges: [
    { id: "e1", source: "process-ew", target: "material-ni", type: "uses_material", trust: 5 },
    { id: "e2", source: "process-ew", target: "material-catholyte", type: "uses_material", trust: 4 },
    { id: "e3", source: "process-ew", target: "equipment-cell", type: "uses_equipment", trust: 4 },
    { id: "e4", source: "process-ew", target: "parameter-flow", type: "has_parameter", trust: 4 },
    { id: "e5", source: "technology-loop", target: "process-ew", type: "has_result", trust: 4 },
    { id: "e6", source: "process-ew", target: "publication-review", type: "described_in", trust: 4 },
    { id: "e7", source: "expert-evgrafova", target: "publication-review", type: "described_in", trust: 4 },
    { id: "e8", source: "process-smelting", target: "phase-matte", type: "has_result", trust: 5 },
    { id: "e9", source: "process-smelting", target: "phase-slag", type: "has_result", trust: 5 },
  ],
};
