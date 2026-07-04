// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

// Root component: three-menu data console with lightweight, typed
// state-based view switching (Home / Source / Milvus). The mysqladmin
// menu item lives in NavBar as an external link to /mysql/.
import { useState } from "react";
import NavBar, { type ViewId } from "./components/NavBar";
import Home from "./views/Home";
import SourceView from "./views/SourceView";
import MilvusView from "./views/MilvusView";
import { ThemeProvider } from "./components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
  const [view, setView] = useState<ViewId>("home");

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background text-foreground">
        <NavBar current={view} onNavigate={setView} />
        <main>
          {view === "home" && <Home />}
          {view === "source" && <SourceView />}
          {view === "milvus" && <MilvusView />}
        </main>
        <Toaster richColors position="bottom-right" />
      </div>
    </ThemeProvider>
  );
}
