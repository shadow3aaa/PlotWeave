import { Routes, Route } from "react-router-dom";
import ProjectListPage from "./pages/ProjectListPage";
import OutlinePage from "./pages/OutlinePage";
import ProjectLayout from "./layouts/ProjectLayout";

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectListPage />} />
      <Route path="/projects" element={<ProjectListPage />} />

      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route index element={<OutlinePage />} />
        <Route path="outline" element={<OutlinePage />} />
      </Route>
    </Routes>
  );
}

export default App;
