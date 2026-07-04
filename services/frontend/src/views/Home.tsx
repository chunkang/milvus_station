// Landing / Main page: explains the PURPOSE and ARCHITECTURE of milvus_station.
// Fully offline & CSP-safe — text, shadcn components, lucide icons and CSS only.
// (No external images, fonts or CDN assets.)
import type { ComponentType } from "react";
import {
  ArrowRight,
  Boxes,
  BrainCircuit,
  Container,
  Database,
  ExternalLink,
  Globe,
  HardDrive,
  Info,
  KeyRound,
  Layers,
  MoveRight,
  Network,
  Search,
  Server,
  Workflow,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

type Icon = ComponentType<{ className?: string }>;

/** A single labelled node in the visual flow diagrams. */
function FlowNode({
  icon: IconCmp,
  label,
  sub,
  tone = "default",
}: {
  icon: Icon;
  label: string;
  sub?: string;
  tone?: "default" | "primary" | "accent";
}) {
  const toneClass =
    tone === "primary"
      ? "border-primary/40 bg-primary/10 text-foreground"
      : tone === "accent"
        ? "border-emerald-500/40 bg-emerald-500/10 text-foreground"
        : "border-border bg-muted/40 text-foreground";
  return (
    <div
      className={`flex min-w-[9rem] flex-1 flex-col items-center gap-1.5 rounded-lg border px-3 py-3 text-center ${toneClass}`}
    >
      <IconCmp className="size-6 text-muted-foreground" />
      <span className="text-sm font-medium leading-tight">{label}</span>
      {sub ? (
        <span className="text-xs text-muted-foreground">{sub}</span>
      ) : null}
    </div>
  );
}

/** Directional arrow that flips from vertical (mobile) to horizontal (>=md). */
function FlowArrow({ label }: { label?: string }) {
  return (
    <div
      aria-hidden="true"
      className="flex shrink-0 flex-col items-center justify-center gap-0.5 py-1 text-muted-foreground md:py-0"
    >
      <MoveRight className="hidden size-5 md:block" />
      <ArrowRight className="size-5 rotate-90 md:hidden" />
      {label ? (
        <span className="text-[10px] font-medium uppercase tracking-wide">
          {label}
        </span>
      ) : null}
    </div>
  );
}

const COMPONENTS: { icon: Icon; name: string; role: string }[] = [
  {
    icon: Network,
    name: "nginx",
    role: "Ingress reverse proxy on :38005 routing to every service.",
  },
  {
    icon: Layers,
    name: "React + shadcn frontend",
    role: "This admin console served at / for browsing and search.",
  },
  {
    icon: Server,
    name: "FastAPI backend",
    role: "REST API at /api driving browse, embedding and indexing.",
  },
  {
    icon: Database,
    name: "MariaDB",
    role: "Relational store holding the source text you want to search.",
  },
  {
    icon: HardDrive,
    name: "phpMyAdmin",
    role: "Web MySQL admin mounted at /mysql for direct DB access.",
  },
  {
    icon: BrainCircuit,
    name: "Ollama (Llama)",
    role: "Runs nomic-embed-text to turn text into 768-dim vectors.",
  },
  {
    icon: Boxes,
    name: "Milvus + etcd + minio",
    role: "Vector database that indexes embeddings for similarity search.",
  },
];

const USAGE: { icon: Icon; title: string; steps: string[] }[] = [
  {
    icon: Database,
    title: "Source",
    steps: [
      "Browse MariaDB databases and tables.",
      "Import the bundled sample tables for milvus_station.",
      "Index any text column into Milvus.",
      "Test semantic search against the indexed column.",
    ],
  },
  {
    icon: Boxes,
    title: "Milvus",
    steps: [
      "Browse existing vector collections and their entities.",
      "Run a test search to preview meaning-based matches.",
    ],
  },
  {
    icon: HardDrive,
    title: "mysqladmin",
    steps: [
      "Opens phpMyAdmin in a new tab.",
      "Full SQL access to inspect or edit source data.",
    ],
  },
];

export default function Home() {
  return (
    <section aria-label="Main" className="mx-auto max-w-6xl px-4 pb-16">
      <div className="flex flex-col gap-6">
        {/* Hero */}
        <Card className="overflow-hidden">
          <CardHeader>
            <Badge variant="secondary" className="w-fit">
              Semantic vector-search platform
            </Badge>
            <CardTitle className="text-3xl font-semibold tracking-tight sm:text-4xl">
              milvus_station
            </CardTitle>
            <CardDescription className="max-w-3xl text-base">
              Turn plain text in MariaDB into meaning with Llama embeddings and
              search it by similarity in Milvus — all served through a single
              Docker stack.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="gap-1.5">
                <Database className="size-3.5" /> MariaDB source
              </Badge>
              <Badge variant="outline" className="gap-1.5">
                <BrainCircuit className="size-3.5" /> Llama embeddings
              </Badge>
              <Badge variant="outline" className="gap-1.5">
                <Boxes className="size-3.5" /> Milvus vectors
              </Badge>
              <Badge variant="outline" className="gap-1.5">
                <Container className="size-3.5" /> One Docker stack
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* What it does */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Info className="size-5 text-muted-foreground" />
              What it does
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              You store text in MySQL/MariaDB, then generate embeddings for it
              with a Llama model running locally through Ollama. Those vectors
              are indexed in Milvus, giving you fast semantic — meaning-based —
              similarity search instead of plain keyword matching.
            </p>
            <p>
              Everything is browsable from this console: pick a source column,
              index it, and immediately test how well semantic search retrieves
              related rows. No cloud services, no external calls — the whole
              pipeline runs inside one self-contained Docker stack.
            </p>
          </CardContent>
        </Card>

        {/* Architecture */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Workflow className="size-5 text-muted-foreground" />
              Architecture
            </CardTitle>
            <CardDescription>
              How requests are routed and how data flows through the pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-8">
            {/* Ingress routing */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-foreground">
                Request routing
              </p>
              <div className="flex flex-col items-stretch gap-3 md:flex-row md:items-center">
                <FlowNode icon={Globe} label="Browser" />
                <FlowArrow />
                <FlowNode
                  icon={Network}
                  label="nginx"
                  sub="ingress :38005"
                  tone="primary"
                />
                <FlowArrow />
                <div className="grid flex-[2] gap-2 sm:grid-cols-3">
                  <FlowNode icon={Layers} label='React console "/"' />
                  <FlowNode icon={HardDrive} label='phpMyAdmin "/mysql"' />
                  <FlowNode icon={Server} label='FastAPI "/api"' />
                </div>
              </div>
            </div>

            <Separator />

            {/* Data pipeline */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-foreground">
                Data pipeline
              </p>
              <div className="flex flex-col items-stretch gap-2 md:flex-row md:items-center">
                <FlowNode
                  icon={Database}
                  label="MariaDB"
                  sub="source text"
                />
                <FlowArrow />
                <FlowNode icon={Server} label="FastAPI" sub="orchestrates" />
                <FlowArrow label="embed" />
                <FlowNode
                  icon={BrainCircuit}
                  label="Ollama · Llama"
                  sub="nomic-embed-text · 768-dim"
                  tone="accent"
                />
                <FlowArrow label="index" />
                <FlowNode
                  icon={Boxes}
                  label="Milvus"
                  sub="etcd + minio"
                  tone="primary"
                />
                <FlowArrow />
                <FlowNode
                  icon={Search}
                  label="Semantic results"
                  tone="accent"
                />
              </div>
            </div>

            <Separator />

            {/* Component roles */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-foreground">Components</p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {COMPONENTS.map(({ icon: IconCmp, name, role }) => (
                  <div
                    key={name}
                    className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3"
                  >
                    <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground ring-1 ring-border">
                      <IconCmp className="size-4" />
                    </span>
                    <div className="space-y-0.5">
                      <p className="text-sm font-medium text-foreground">
                        {name}
                      </p>
                      <p className="text-xs text-muted-foreground">{role}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* How to use */}
        <div className="grid gap-4 md:grid-cols-3">
          {USAGE.map(({ icon: IconCmp, title, steps }) => (
            <Card key={title}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <IconCmp className="size-5 text-muted-foreground" />
                  {title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {steps.map((step) => (
                    <li key={step} className="flex items-start gap-2">
                      <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Default credentials note */}
        <Card className="border-dashed">
          <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="flex items-center gap-2 text-sm font-medium text-foreground">
              <KeyRound className="size-4 text-muted-foreground" />
              Default MySQL credentials
            </p>
            <p className="text-sm text-muted-foreground">
              ID:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
                milvus
              </code>{" "}
              / Password:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
                milvus
              </code>{" "}
              <span className="inline-flex items-center gap-1 text-xs">
                <ExternalLink className="size-3" /> used by phpMyAdmin login
              </span>
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
