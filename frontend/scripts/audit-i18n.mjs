import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

// An inventory of literal JSX copy, not a claim that dynamic/API/model text is translated.
const roots = process.argv.slice(2).filter(a => a !== '--json');
const findings = [];
function walk(entry) {
  const stat = fs.statSync(entry);
  if (stat.isDirectory()) {
    for (const name of fs.readdirSync(entry).sort()) {
      if (!['__tests__', 'node_modules', 'i18n'].includes(name)) walk(path.join(entry, name));
    }
    return;
  }
  if (!entry.endsWith('.tsx') || /\.(test|spec)\./.test(entry)) return;
  const source = ts.createSourceFile(entry, fs.readFileSync(entry, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function report(node, text, kind) {
    text = text.replace(/\s+/g, ' ').trim();
    if (!/\p{L}/u.test(text)) return;
    findings.push({ file: entry, line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1, kind, text });
  }
  function visit(node) {
    if (ts.isJsxText(node)) report(node, node.text, 'text');
    if (ts.isJsxAttribute(node) && ['title', 'placeholder', 'alt', 'aria-label', 'aria-description'].includes(node.name.getText(source)) && node.initializer && ts.isStringLiteral(node.initializer)) report(node, node.initializer.text, 'attribute');
    if (ts.isJsxExpression(node) && node.expression) {
      function expression(child) {
        if (ts.isStringLiteral(child) || ts.isNoSubstitutionTemplateLiteral(child)) report(child, child.text, 'expression');
        else if (ts.isTemplateExpression(child)) {
          report(child, child.head.text + child.templateSpans.map(s => '{…}' + s.literal.text).join(''), 'template');
        } else if (ts.isConditionalExpression(child)) { expression(child.whenTrue); expression(child.whenFalse); }
      }
      expression(node.expression);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
}
for (const root of roots.length ? roots : ['src']) walk(root);
if (process.argv.includes('--json')) process.stdout.write(JSON.stringify(findings, null, 2) + '\n');
else { for (const f of findings) console.log(`${f.file}:${f.line} [${f.kind}] ${f.text}`); console.log(`${findings.length} literal JSX copy candidates (dynamic copy needs manual review).`); }
