// Top navigation bar for the data console.
// "Main", "Source" and "Milvus" switch the SPA view; "mysqladmin" opens
// /mysql/ in a new tab and does NOT change the current view.
import { Database, ExternalLink, Home, Layers, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useTheme } from "@/components/theme-provider";

export type ViewId = "home" | "source" | "milvus";

interface NavBarProps {
  current: ViewId;
  onNavigate: (view: ViewId) => void;
}

export default function NavBar({ current, onNavigate }: NavBarProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 mb-8 border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4"
      >
        <button
          type="button"
          onClick={() => onNavigate("home")}
          className="mr-2 flex items-center gap-2 rounded-md px-1 text-base font-semibold tracking-tight text-foreground transition-colors hover:text-primary"
        >
          <span
            aria-hidden="true"
            className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground"
          >
            <Layers className="size-4" />
          </span>
          milvus_station
        </button>

        <Separator orientation="vertical" className="mr-1 !h-6" />

        <Button
          type="button"
          variant={current === "home" ? "secondary" : "ghost"}
          size="sm"
          aria-current={current === "home" ? "page" : undefined}
          onClick={() => onNavigate("home")}
        >
          <Home className="size-4" />
          Main
        </Button>

        <Button
          type="button"
          variant={current === "source" ? "secondary" : "ghost"}
          size="sm"
          aria-current={current === "source" ? "page" : undefined}
          onClick={() => onNavigate("source")}
        >
          <Database className="size-4" />
          Source
        </Button>

        <Button
          type="button"
          variant={current === "milvus" ? "secondary" : "ghost"}
          size="sm"
          aria-current={current === "milvus" ? "page" : undefined}
          onClick={() => onNavigate("milvus")}
        >
          <Layers className="size-4" />
          Milvus
        </Button>

        <Button asChild variant="ghost" size="sm">
          <a href="/mysql/" target="_blank" rel="noopener noreferrer">
            mysqladmin
            <ExternalLink className="size-3.5" />
          </a>
        </Button>

        <div className="ml-auto">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            onClick={toggleTheme}
          >
            {theme === "dark" ? (
              <Sun className="size-4" />
            ) : (
              <Moon className="size-4" />
            )}
          </Button>
        </div>
      </nav>
    </header>
  );
}
