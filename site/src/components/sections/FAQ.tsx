import SectionHeader from '@/components/ui/SectionHeader';

// Answers are plain text on purpose: they render inside <details> and are
// reused verbatim in the FAQPage JSON-LD below, so one string feeds both the
// page and the structured data. Every figure is sourced in site/claims.json.
const faqs = [
    {
        q: 'Does NeuralMind work with Claude Code, Cursor, Codex and other agents?',
        a: 'NeuralMind runs as a standard MCP server, so any MCP-compatible agent can use it. Claude Code is tested end to end and also gets lifecycle hooks — memory at session start, prompt-time recall and a stale-decision guard. Cursor, Cline, Continue and Codex connect through the same protocol; the MCP handshake is verified against Codex, but we have not driven those agents end to end in CI, so the README labels them theoretical. "neuralmind install-mcp" registers the server with Claude Code (add --client for Cursor, Cline, VS Code or Claude Desktop), and other clients point their MCP config at "neuralmind-mcp". There is also a CLI and a Python API.',
    },
    {
        q: 'How much does NeuralMind reduce Claude Code token usage?',
        a: 'It depends on your repo, so measure it. On the public benchmark — 40 pre-registered queries on requests, click, flask and rich — NeuralMind’s context was 51–242× smaller than pasting every source file, and it found the gold file on all 40. Pasting everything is the easiest baseline to beat: against ripgrep opening its top five files, closer to how an agent works, it was 31–67× smaller, and ripgrep found the gold file on 32 of 40. An agent that reads only the matching lines pays less still, and that is not measured. On private repos, "neuralmind benchmark ." reported 12–50× before v4.5.0, against a fixed 50K-token estimate; it now divides the measured size of your own code, so run it and read yours. That is what reaches the agent’s window, not what a task costs: a pre-registered 20-task pilot ran Claude Code with and without NeuralMind and found no difference in tasks solved or cost per task, because the agent never called NeuralMind’s tools (neuralmind.uk/benchmark/#task-outcomes). NeuralMind no longer claims savings on tool output: its old compression hooks, measured against how Claude Code actually handles hook output, added tokens instead of saving them, so they were switched off (docs.neuralmind.uk/benchmarks/compression.html).',
    },
    {
        q: 'How is this different from RAG or a vector database?',
        a: 'Plain RAG retrieves text chunks that look similar to the question. NeuralMind keeps a graph of your code — symbols, imports, call edges — assembles a structured context from it (project map, relevant symbols, their callers), and adds a synapse layer that learns which files you use together. On pure findability a vector index is a strong baseline: in the public benchmark, NeuralMind’s own index alone (top 8 entries, names and docstrings, no code) costs fewer tokens on every repo and still ranks the gold file higher on flask and rich, though NeuralMind’s recall is now at or above it everywhere — and we publish that. NeuralMind spends its extra tokens on context an agent can answer from, and on memory that persists between sessions.',
    },
    {
        q: 'Does NeuralMind get better the more I use it?',
        a: 'It is built to: the synapse layer strengthens links between files you use together and lets unused ones fade, and recall uses those links to re-rank results. What is shown so far is narrower. CI checks that learned recall never lowers the hit rate, on a ~500-line fixture, which shows direction rather than size. Nothing we publish yet shows it improving retrieval on a real codebase over weeks of use, and a 20-task pilot found agents solved the same tasks at the same cost with and without NeuralMind. You can measure the first on your own repo: write down questions with the file that answers each (past incidents, phrased as the symptom), then run "neuralmind eval . --synapse-ab" (v4.14.0+), which runs them with synapse recall on and off and records the difference each time.',
    },
    {
        q: 'What does NeuralMind remember, and what does it forget?',
        a: 'It remembers your code, which files you use together, the decisions recorded about the code and what your last session was doing. It keeps no profile of you or your preferences; those belong in CLAUDE.md or your agent’s own memory. Learning on a feature branch goes into that branch’s own namespace automatically (v0.24.0+), so it stays out of the memory the default branch uses. The code index does not decay. Learned associations do, on a 30-day default half-life that each one adjusts between 3 and 120 days by how often it was used, and an association used five or more times keeps a floor. Every agent gets the same plain-text context, and Claude Code gets the most from it through its hooks. Each answer, with the code behind it: neuralmind.uk/what-it-remembers/.',
    },
    {
        q: 'How is NeuralMind different from CLAUDE.md or Cursor rules?',
        a: 'CLAUDE.md and rules files are instructions you write and maintain by hand. NeuralMind is memory the agent builds by working: a queryable index of the whole codebase plus associations learned from use. The two compose — NeuralMind exports its learned hub files and associations to SYNAPSE_MEMORY.md, which Claude Code loads at session start and your CLAUDE.md can import.',
    },
    {
        q: 'Does any of my code leave my machine?',
        a: 'By default, NeuralMind itself sends no telemetry and transmits no repository content off your machine — the graph, embeddings and synapse store live in your project directory. Its only default outbound request downloads a public embedding model on first build (again only if the cached copy is removed), and you can pre-seed it for air-gapped installs. One opt-in feature, off by default, sends README and architecture-doc prose to Anthropic under your own API key. What does leave is the context slice your agent sends to its own model provider, which NeuralMind makes smaller but does not control.',
    },
    {
        q: 'Is NeuralMind free? What does the paid tier buy?',
        a: 'The core is MIT open source, including everything that reduces tokens. A free 1-seat license auto-issues the first time you run "neuralmind wakeup ." — no signup, no expiry — and it unlocks every feature, including shared-memory governance, the hash-chained audit log and self-hosted deployment. NeuralMind Team ($29/user/mo, annual, 5–50 seats) buys seats beyond one, priority support and an annual invoice. You pay for seats and support, not for features.',
    },
    {
        q: 'How does team memory work?',
        a: 'Run "neuralmind memory publish" and the project’s learned associations are written to .neuralmind-team-memory.json at the repo root — learned weights, no source code. Commit that file, and every teammate’s agent imports it on the next session or build; each association is quality-scored on the way in, and borderline ones wait in a review queue. A new hire’s agent starts already knowing that the auth handlers go with the JWT utilities, instead of relearning it from scratch.',
    },
    {
        q: 'Where does NeuralMind lose?',
        a: 'Five places, all published. On real tasks, a pre-registered 20-task pilot found no difference: 18 of 20 solved with and without NeuralMind, at the same cost per task, and the agent never called NeuralMind’s tools. It finds all 40 public-benchmark queries, but 40 is a small sample: on a 150-question retrieval eval it misses the gold file in the top five on 10, most of them where vector search ranks that file outside the 20 candidates NeuralMind re-ranks. If all you need is to locate a file, a bare vector index is cheaper, and on flask and rich it still ranks the gold file higher. On the CI fixture it took until v4.12.0 to beat naive truncation at the same token budget (+0.265 at v4.12.0, 0.839 vs 0.574, measured on one machine; v4.3.4 was a loss, −0.054), CI gates only that it stays above −0.10, and that fixture is small. And the synapse layer needs real use to learn: a fresh install has no learned associations yet.',
    },
    {
        q: 'What languages does it support?',
        a: 'Ten out of the box via bundled tree-sitter grammars: Python, TypeScript (and JavaScript/JSX, parsed with the TypeScript grammars), Go, Rust, Java, C, C++, C#, Ruby and PHP — plus OpenAPI, SQL DDL and Protocol Buffers schema files. Markdown and text can be indexed too, as their own content project.',
    },
];

const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
        '@type': 'Question',
        name: faq.q,
        acceptedAnswer: { '@type': 'Answer', text: faq.a },
    })),
};

export default function FAQ() {
    return (
        <section id="faq" className="relative py-16 md:py-32 px-4 md:px-6">
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
            />
            <div className="max-w-3xl mx-auto">
                <SectionHeader eyebrow="FAQ" title="Common questions" />

                <div className="space-y-3">
                    {faqs.map((faq, i) => (
                        // <details> keeps every answer in the served HTML.
                        // The previous accordion rendered answers only while
                        // open ({openIndex === i && ...}), so the static export
                        // carried 11 questions and no answer text at all —
                        // invisible to crawlers and to anything quoting the
                        // page. It is also keyboard-accessible and needs no JS,
                        // which is why this component is no longer a client one.
                        <details key={i} className="card rounded-card overflow-hidden group">
                            <summary className="w-full px-6 py-5 flex items-center justify-between text-left cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                                <h3 className="font-semibold text-white pr-4 text-base">{faq.q}</h3>
                                <svg
                                    className="w-5 h-5 text-muted shrink-0 transition-transform duration-200 group-open:rotate-180"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                    aria-hidden="true"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </summary>
                            <div className="px-6 pb-5 pt-0">
                                <p className="text-muted leading-relaxed text-sm">{faq.a}</p>
                            </div>
                        </details>
                    ))}
                </div>
            </div>
        </section>
    );
}
