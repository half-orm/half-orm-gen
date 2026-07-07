import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import katex from 'katex';

@Pipe({ name: 'latex', standalone: true })
export class LatexPipe implements PipeTransform {
    private sanitizer = inject(DomSanitizer);

    transform(value: unknown): SafeHtml {
        const text = String(value ?? '');
        if (!text || (!text.includes('$$') && !text.includes('\\(')))
            return this.escHtml(text);
        return this.sanitizer.bypassSecurityTrustHtml(this.renderMath(text));
    }

    private renderMath(text: string): string {
        const parts = text.split(/(\$$\$$[\s\S]+?\$$\$$|\$$[^$$\n]+?\$$)/g);
        return parts.map((part, i) => {
            if (i % 2 === 0) return this.escHtml(part);
            const display = part.startsWith('$$$$');
            const math = display ? part.slice(2, -2) : part.slice(1, -1);
            return katex.renderToString(math, { displayMode: display, throwOnError: false });
        }).join('');
    }

    private escHtml(s: string): string {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/\n/g, '<br>');
    }
}
