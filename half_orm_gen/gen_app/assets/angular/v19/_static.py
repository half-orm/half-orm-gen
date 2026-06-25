_PACKAGE_JSON = """\
{{
  "name": "{project_name}",
  "version": "0.0.1",
  "private": true,
  "scripts": {{
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development"
  }},
  "dependencies": {{
    "@angular/animations": "^22.0.0",
    "@angular/common": "^22.0.0",
    "@angular/compiler": "^22.0.0",
    "@angular/core": "^22.0.0",
    "@angular/forms": "^22.0.0",
    "@angular/platform-browser": "^22.0.0",
    "@angular/platform-browser-dynamic": "^22.0.0",
    "@angular/router": "^22.0.0",
    "katex": "^0.16.0",
    "rxjs": "~7.8.0",
    "tslib": "^2.3.0",
    "zone.js": "~0.15.0"
  }},
  "devDependencies": {{
    "@angular/build": "^22.0.0",
    "@angular/cli": "^22.0.0",
    "@angular/compiler-cli": "^22.0.0",
    "@types/katex": "^0.16.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "~6.0.0"
  }}
}}
"""

_ANGULAR_JSON = """\
{{
  "$schema": "./node_modules/@angular/cli/lib/config/schema.json",
  "version": 1,
  "projects": {{
    "{project_name}": {{
      "projectType": "application",
      "root": "",
      "sourceRoot": "src",
      "architect": {{
        "build": {{
          "builder": "@angular/build:application",
          "options": {{
            "outputPath": "dist/{project_name}",
            "index": "src/index.html",
            "browser": "src/main.ts",
            "polyfills": ["zone.js"],
            "tsConfig": "tsconfig.app.json",
            "assets": [{{"glob": "**/*", "input": "public"}}],
            "styles": ["src/styles.css"],
            "scripts": []
          }},
          "configurations": {{
            "production": {{
              "budgets": [
                {{"type": "initial", "maximumWarning": "500kB", "maximumError": "1MB"}},
                {{"type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB"}}
              ],
              "outputHashing": "all"
            }},
            "development": {{
              "optimization": false,
              "extractLicenses": false,
              "sourceMap": true
            }}
          }},
          "defaultConfiguration": "production"
        }},
        "serve": {{
          "builder": "@angular/build:dev-server",
          "configurations": {{
            "production": {{"buildTarget": "{project_name}:build:production"}},
            "development": {{
              "buildTarget": "{project_name}:build:development",
              "proxyConfig": "proxy.conf.json"
            }}
          }},
          "defaultConfiguration": "development"
        }}
      }}
    }}
  }}
}}
"""

_TSCONFIG = """\
{
  "compileOnSave": false,
  "compilerOptions": {
    "outDir": "./dist/out-tsc",
    "strict": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "moduleResolution": "bundler",
    "importHelpers": true,
    "target": "ES2022",
    "module": "ES2022",
    "lib": ["ES2022", "dom"]
  },
  "angularCompilerOptions": {
    "enableI18nLegacyMessageIdFormat": false,
    "strictInjectionParameters": true,
    "strictInputAccessModifiers": true,
    "strictTemplates": true
  }
}
"""

_TSCONFIG_APP = """\
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "outDir": "./out-tsc/app",
    "types": []
  },
  "files": ["src/main.ts"],
  "include": ["src/**/*.d.ts"]
}
"""

_INDEX_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{project_title}</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <app-root></app-root>
</body>
</html>
"""

_STYLES_CSS = """\
@import 'katex/dist/katex.min.css';
@tailwind base;
@tailwind components;
@tailwind utilities;
"""

_LATEX_PIPE = """\
import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import katex from 'katex';

@Pipe({ name: 'latex', standalone: true })
export class LatexPipe implements PipeTransform {
    private sanitizer = inject(DomSanitizer);

    transform(value: unknown): SafeHtml {
        const text = String(value ?? '');
        if (!text || (!text.includes('$') && !text.includes('\\\\(')))
            return this.escHtml(text);
        return this.sanitizer.bypassSecurityTrustHtml(this.renderMath(text));
    }

    private renderMath(text: string): string {
        const parts = text.split(/(\\$\\$[\\s\\S]+?\\$\\$|\\$[^$\\n]+?\\$)/g);
        return parts.map((part, i) => {
            if (i % 2 === 0) return this.escHtml(part);
            const display = part.startsWith('$$');
            const math = display ? part.slice(2, -2) : part.slice(1, -1);
            return katex.renderToString(math, { displayMode: display, throwOnError: false });
        }).join('');
    }

    private escHtml(s: string): string {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/\\n/g, '<br>');
    }
}
"""

_TAILWIND_CONFIG = """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: { extend: {} },
  plugins: []
};
"""

_POSTCSS_CONFIG = """\
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} }
};
"""

_MAIN_TS = """\
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

bootstrapApplication(AppComponent, appConfig)
  .catch(err => console.error(err));
"""

_APP_CONFIG_TS = """\
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
  ]
};
"""

_STATE_REGISTRY = """\
const _fns: Array<() => void> = [];
export function registerClear(fn: () => void): void { _fns.push(fn); }
export function clearAllStates(): void { _fns.forEach(fn => fn()); }
"""


def _proxy_conf(version_prefix: str) -> str:
    prefix = version_prefix or '/api'
    return (
        '{\n'
        f'  "{prefix}": {{\n'
        '    "target": "http://localhost:8000",\n'
        '    "secure": false,\n'
        '    "ws": true\n'
        '  }\n'
        '}\n'
    )
