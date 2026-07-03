import type { AnalysisMode, DemoRole, EntityType, Geography, SourceType } from "./types";

export const modeLabels: Record<AnalysisMode | "auto", string> = { auto: "Авто", answer: "Ответ", literature_review: "Литобзор", comparison: "Сравнение" };
export const geographyLabels: Record<Geography, string> = { Russia: "Россия", CIS: "СНГ", Foreign: "Зарубежная", Global: "Глобальная", Unknown: "Не определена" };
export const sourceTypeLabels: Record<SourceType, string> = { scientific_article: "Научная статья", patent: "Патент", internal_report: "Внутренний отчёт", conference_paper: "Материалы конференции", journal_issue: "Журнал", review: "Обзор" };
export const roleLabels: Record<DemoRole, string> = { researcher: "Исследователь", analyst: "Аналитик", project_lead: "Руководитель проекта", admin: "Администратор", external_partner: "Внешний партнёр" };
export const entityLabels: Record<EntityType, string> = { Material: "Материал", Process: "Процесс", Equipment: "Оборудование", Facility: "Площадка", Experiment: "Эксперимент", Publication: "Публикация", Expert: "Эксперт", Parameter: "Параметр", Phase: "Фаза", Technology: "Технология" };
