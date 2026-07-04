// Minimal static landing page for the milvus_station frontend scaffold.
// Renders without any backend dependency (SPEC-INFRA-001, TASK-004).
export default function App() {
  return (
    <main>
      <h1>hello world</h1>
      <p>
        <a href="/mysql/" target="_blank" rel="noopener noreferrer">mysql</a>
      </p>
      <p>
        Default MySQL credentials — ID: <code>milvus</code> / Password:{" "}
        <code>milvus</code>
      </p>
    </main>
  );
}
