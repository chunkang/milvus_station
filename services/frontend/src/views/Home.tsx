// Landing view: preserves the original "hello world" + default credentials,
// presented inside a tidy shadcn Card.
import { Database, KeyRound, Layers } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <section aria-label="Home" className="mx-auto max-w-6xl px-4 pb-16">
      <div className="flex flex-col gap-6">
        <Card className="overflow-hidden">
          <CardHeader>
            <Badge variant="secondary" className="w-fit">
              milvus_station
            </Badge>
            <CardTitle className="text-3xl font-semibold tracking-tight">
              hello world
            </CardTitle>
            <CardDescription className="max-w-2xl text-base">
              Welcome to the milvus_station data console. Use the navigation
              above to browse MySQL sources, inspect Milvus collections, or open
              the database admin.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-border bg-muted/40 p-4">
              <p className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                <KeyRound className="size-4 text-muted-foreground" />
                Default MySQL credentials
              </p>
              <p className="text-sm text-muted-foreground">
                ID:{" "}
                <code className="rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  milvus
                </code>{" "}
                / Password:{" "}
                <code className="rounded bg-background px-1.5 py-0.5 font-mono text-foreground">
                  milvus
                </code>
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Database className="size-5 text-muted-foreground" />
                Source
              </CardTitle>
              <CardDescription>
                Browse MySQL databases and tables, then index any text column
                into Milvus.
              </CardDescription>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Layers className="size-5 text-muted-foreground" />
                Milvus
              </CardTitle>
              <CardDescription>
                Inspect vector collections and page through their stored
                entities.
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </div>
    </section>
  );
}
