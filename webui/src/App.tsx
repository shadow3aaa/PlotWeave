import { Routes, Route } from "react-router-dom";
import ProjectListPage from "./pages/ProjectListPage";
import OutlinePage from "./pages/OutlinePage";
import ProjectLayout from "./layouts/ProjectLayout";
import WorldSetupPage from "./pages/WorldSetupPage";
import ChapteringPage from "./pages/ChapteringPage";
import ChapterWritingPage from "./pages/ChapterWritingPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectListPage />} />
      <Route path="/projects" element={<ProjectListPage />} />

      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route index element={<OutlinePage />} />
        <Route path="outline" element={<OutlinePage />} />
        <Route path="world-setup" element={<WorldSetupPage />} />
        <Route path="chaptering" element={<ChapteringPage />} />
        <Route path="chapter-writing" element={<ChapterWritingPage />} />
      </Route>
    </Routes>
  );
}

export default App;
