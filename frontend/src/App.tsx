import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useParams } from "react-router-dom";
import Library from "./pages/Library";
import Workspace from "./pages/Workspace";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/doc/:id" element={<WorkspaceRoute />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function WorkspaceRoute() {
  const { id } = useParams<{ id: string }>();
  return id ? <Workspace id={id} /> : <Library />;
}
