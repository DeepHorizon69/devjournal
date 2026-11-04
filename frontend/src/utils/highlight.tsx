import React from 'react';
import { SnippetSegment } from '../types';

function decodeHtmlEntities(input: string): string {
  return input
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
}

/**
 * Safely renders FTS5 search snippets into React nodes without ever using dangerouslySetInnerHTML.
 * Prefers structured `segments` produced from collision-resistant per-query nonce markers on the backend.
 */
export function renderHighlightedSnippet(
  snippet: string,
  segments?: SnippetSegment[]
): React.ReactNode {
  if (segments && segments.length > 0) {
    return segments.map((seg, idx) =>
      seg.highlight ? (
        <mark
          key={idx}
          className="bg-accent/25 text-accent font-medium px-0.5 rounded"
        >
          {seg.text}
        </mark>
      ) : (
        <React.Fragment key={idx}>{seg.text}</React.Fragment>
      )
    );
  }

  if (!snippet) {
    return null;
  }

  const parts = snippet.split(/(<mark>[\s\S]*?<\/mark>)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('<mark>') && part.endsWith('</mark>')) {
      const inner = decodeHtmlEntities(part.slice(6, -7));
      return (
        <mark
          key={idx}
          className="bg-accent/25 text-accent font-medium px-0.5 rounded"
        >
          {inner}
        </mark>
      );
    }
    return <React.Fragment key={idx}>{decodeHtmlEntities(part)}</React.Fragment>;
  });
}
