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
        a: 'It depends on your repo, so measure it. On the public benchmark — 40 pre-registered queries on requests, click, flask and rich — NeuralMind’s context was 45–261× smaller than pasting every source file, at 93.75% mean gold-file recall. On private repos, "neuralmind benchmark ." has reported 12–50× against its fixed 50K-token naive baseline. That is the retrieval slice of your bill; end-to-end savings are smaller, because generation, conversation history and tool output cost tokens too — the published business case models that honestly. NeuralMind no longer claims savings on tool output: its old compression hooks, measured against how Claude Code actually handles hook output, added tokens instead of saving them, so they were switched off (docs.neuralmind.uk/benchmarks/compression.html).',
    },
    {
        q: 'How is this different from RAG or a vector database?',
        a: 'Plain RAG retrieves text chunks that look similar to the question. NeuralMind keeps a graph of your code — symbols, imports, call edges — assembles a structured context from it (project map, relevant symbols, their callers), and adds a synapse layer that learns which files you use together. On pure findability a tuned vector index is a strong baseline: in the public benchmark it matches or beats NeuralMind’s recall at fewer tokens on every repo, and we publish that. NeuralMind spends its extra tokens on context an agent can answer from, and on memory that persists between sessions.',
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
        a: 'Four places, all published. It misses 4 of the 40 public-benchmark queries — mostly two-file questions where it retrieves one of the two files — and flask is its weakest repo at 85% recall. If all you need is to locate a file, a bare vector index is cheaper. On the CI fixture, naive truncation at the same token budget currently keeps slightly more gold facts than NeuralMind’s context (−0.054). And the synapse layer needs real use to learn: a fresh install has no learned associations yet.',
    },
    {
        q: 'Why not just use Cursor, Windsurf or Aider memory?',
        a: 'Built-in memory is tied to one agent. NeuralMind is agent-agnostic: the same memory serves Claude Code, Codex, Cursor and anything else that speaks MCP, survives switching tools, lives in your repo, and is inspectable. It composes with those tools rather than replacing them.',
    },
    {
        q: 'What languages does it support?',
        a: 'Ten out of the box via bundled tree-sitter grammars: Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby and PHP — plus OpenAPI, SQL DDL and Protocol Buffers schema files. Markdown and text can be indexed too, as their own content project.',
    },
    {
        q: 'What is the business case for a team?',
        a: 'Two lines: the measured token reduction (free — verify it on your own repo in about 15 minutes) and time lost to context-limit thrashing and re-prompting, which the business case models but does not measure. The full model and its assumptions are published, and the free assessment measures both in your numbers. If your workload is generation-heavy or prompt caching already covers you, we say so.',
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
                        <details key={i} className="card rounded-xl overflow-hidden group">
                            <summary className="w-full px-6 py-5 flex items-center justify-between text-left cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                                <h3 className="font-semibold text-white pr-4 text-base">{faq.q}</h3>
                                <svg
                                    className="w-5 h-5 text-slate-400 shrink-0 transition-transform duration-200 group-open:rotate-180"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                    aria-hidden="true"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </summary>
                            <div className="px-6 pb-5 pt-0">
                                <p className="text-slate-400 leading-relaxed text-sm">{faq.a}</p>
                            </div>
                        </details>
                    ))}
                </div>
            </div>
        </section>
    );
}
