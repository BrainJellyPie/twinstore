import { Fragment, type ReactNode } from "react";

/** Puts React nodes (bold figures, links) where a translated text still has {placeholders}. */
export function richText(text: string, nodes: Record<string, ReactNode>): ReactNode {
  return text.split(/(\{\w+\})/).map((part, index) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1];
    return <Fragment key={index}>{name !== undefined && Object.prototype.hasOwnProperty.call(nodes, name) ? nodes[name] : part}</Fragment>;
  });
}
