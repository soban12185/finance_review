import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => <p className="my-1.5">{children}</p>,
  h1: ({ children }) => <h1 className="mb-2 mt-3 text-lg font-semibold text-slate-900 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-3 text-base font-semibold text-slate-900 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-2.5 text-sm font-semibold text-slate-900 first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1.5 mt-2.5 text-sm font-medium text-slate-900 first:mt-0">{children}</h4>,
  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  table: ({ children }) => (
    <div className="my-2.5 overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border-b border-slate-100 px-3 py-2 align-top text-slate-700">{children}</td>,
  tr: ({ children }) => <tr className="last:border-b-0">{children}</tr>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  em: ({ children }) => <em className="italic text-slate-700">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline decoration-indigo-200 underline-offset-2 hover:decoration-indigo-600">
      {children}
    </a>
  ),
  code: ({ className, children }) => (
    <code className={`rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[13px] text-slate-800 ${className ?? ""}`}>
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-2.5 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-[13px] leading-relaxed text-slate-100 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-inherit">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-4 border-slate-200 pl-3 text-slate-600">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-slate-200" />,
  input: ({ checked }) => <input type="checkbox" checked={checked} className="mr-1.5" readOnly />,
};

export default function Markdown({ children }: { children: string }) {
  return (
    <div className="min-w-0 text-sm leading-relaxed text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}