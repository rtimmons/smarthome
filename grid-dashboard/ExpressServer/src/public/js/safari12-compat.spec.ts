import {expect} from 'chai';
import {readFileSync} from 'fs';
import {dirname, resolve} from 'path';
import ts from 'typescript';

const indexPath = resolve(__dirname, '..', 'index.html');

const directlyServedFirstPartyScripts = (): string[] => {
    const html = readFileSync(indexPath, 'utf8');
    return Array.from(html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["']/gi))
        .map(match => match[1].split(/[?#]/, 1)[0])
        .filter(source => source.startsWith('js/') && !source.startsWith('js/vendor/'))
        .map(source => resolve(dirname(indexPath), source));
};

const safari12SyntaxProblems = (path: string): string[] => {
    const sourceText = readFileSync(path, 'utf8');
    const sourceFile = ts.createSourceFile(
        path,
        sourceText,
        ts.ScriptTarget.ES2018,
        true,
        ts.ScriptKind.JS
    );
    const parseDiagnostics = (
        sourceFile as ts.SourceFile & {parseDiagnostics: readonly ts.Diagnostic[]}
    ).parseDiagnostics;
    const problems = parseDiagnostics.map(diagnostic =>
        ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')
    );

    const visit = (node: ts.Node): void => {
        const optionalChain = (
            ts.isPropertyAccessExpression(node) ||
            ts.isElementAccessExpression(node) ||
            ts.isCallExpression(node)
        ) && Boolean(node.questionDotToken);
        const logicalOrNullishAssignment = ts.isBinaryExpression(node) && [
            ts.SyntaxKind.QuestionQuestionToken,
            ts.SyntaxKind.QuestionQuestionEqualsToken,
            ts.SyntaxKind.AmpersandAmpersandEqualsToken,
            ts.SyntaxKind.BarBarEqualsToken,
        ].includes(node.operatorToken.kind);

        if (optionalChain) {
            problems.push('optional chaining is newer than Safari 12');
        }
        if (logicalOrNullishAssignment) {
            problems.push('nullish/logical assignment syntax is newer than Safari 12');
        }
        if (ts.isBigIntLiteral(node)) {
            problems.push('BigInt literals are newer than Safari 12');
        }
        if (ts.isPrivateIdentifier(node)) {
            problems.push('private class fields are newer than Safari 12');
        }
        if (ts.isPropertyDeclaration(node)) {
            problems.push('public class fields are newer than Safari 12');
        }
        if (ts.isClassStaticBlockDeclaration(node)) {
            problems.push('class static blocks are newer than Safari 12');
        }
        if (
            ts.isImportDeclaration(node) ||
            ts.isExportDeclaration(node) ||
            ts.isExportAssignment(node)
        ) {
            problems.push('module syntax cannot run in the dashboard classic-script tags');
        }
        if (ts.isRegularExpressionLiteral(node) && /\(\?<([=!])/.test(node.text)) {
            problems.push('regular-expression lookbehind is newer than Safari 12');
        }
        if (ts.isNumericLiteral(node) && node.getText(sourceFile).includes('_')) {
            problems.push('numeric separators are newer than Safari 12');
        }

        ts.forEachChild(node, visit);
    };
    visit(sourceFile);

    return [...new Set(problems)];
};

describe('Safari 12 first-party browser syntax compatibility', () => {
    it('checks every directly served first-party Grid Dashboard script', () => {
        const scripts = directlyServedFirstPartyScripts();
        expect(scripts.length).to.be.greaterThan(0);

        const failures = scripts.flatMap(path =>
            safari12SyntaxProblems(path).map(problem => `${path}: ${problem}`)
        );
        expect(failures, failures.join('\n')).to.deep.equal([]);
    });
});
