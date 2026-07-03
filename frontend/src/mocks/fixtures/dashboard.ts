import type { DashboardData, QualityItemGroup } from "../../domain/types";
import { catholyteAnswer, desalinationAnswer, pgmAnswer } from "./scenarios";

export const dashboard: DashboardData = {
  totals: { documents: 1281, facts: 830409, nodes: 1717, edges: 51184, experts: 285, contradictions: 12, gaps: 37, confidence: 87 },
  byYear: [{ year: 2019, count: 94 }, { year: 2020, count: 108 }, { year: 2021, count: 126 }, { year: 2022, count: 141 }, { year: 2023, count: 155 }, { year: 2024, count: 187 }, { year: 2025, count: 201 }],
  byDomain: [{ name: "Гидрометаллургия", value: 34 }, { name: "Пирометаллургия", value: 27 }, { name: "Горное дело", value: 24 }, { name: "Экология", value: 15 }],
  byGeography: [{ name: "Глобальная", value: 895 }, { name: "Зарубежная", value: 301 }, { name: "Россия", value: 51 }, { name: "Не определена", value: 34 }],
  bySourceType: [{ name: "Конференции", value: 740 }, { name: "Журналы", value: 373 }, { name: "Обзоры", value: 101 }, { name: "Статьи", value: 52 }, { name: "Доклады", value: 15 }],
  coverage: [{ material: "Никель", process: "Электроэкстракция", score: 94 }, { material: "Медь", process: "Плавка", score: 88 }, { material: "Шахтные воды", process: "Очистка", score: 62 }, { material: "МПГ", process: "Распределение", score: 48 }],
  weakTopics: [{ topic: "Закачка шахтных вод: экономика", documents: 2 }, { topic: "МПГ: публикации последних 5 лет", documents: 3 }, { topic: "Кучное выщелачивание в Арктике", documents: 4 }],
};

export const quality: QualityItemGroup = {
  contradictions: [...catholyteAnswer.contradictions],
  validations: [...catholyteAnswer.validations, ...desalinationAnswer.validations],
  gaps: [...catholyteAnswer.gaps, ...desalinationAnswer.gaps, ...pgmAnswer.gaps],
};
