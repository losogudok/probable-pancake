import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { App } from "./App";
import { LoadingBlock } from "../components/ui/Primitives";

const SearchPage = lazy(() => import("../features/search/SearchPage").then((module) => ({ default: module.SearchPage })));
const GraphPage = lazy(() => import("../features/graph/GraphPage").then((module) => ({ default: module.GraphPage })));
const SourcesPage = lazy(() => import("../features/sources/SourcesPage").then((module) => ({ default: module.SourcesPage })));
const QualityPage = lazy(() => import("../features/quality/QualityPage").then((module) => ({ default: module.QualityPage })));
const AnalyticsPage = lazy(() => import("../features/analytics/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const page = (node: React.ReactNode) => <Suspense fallback={<LoadingBlock label="Открываем раздел"/>}>{node}</Suspense>;

const router = createBrowserRouter([{ path: "/", element: <App />, children: [
  { index: true, element: page(<SearchPage />) }, { path: "graph", element: page(<GraphPage />) },
  { path: "sources", element: page(<SourcesPage />) }, { path: "quality", element: page(<QualityPage />) },
  { path: "analytics", element: page(<AnalyticsPage />) },
]}]);
export function AppRouter() { return <RouterProvider router={router} />; }
