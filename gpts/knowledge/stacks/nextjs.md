# Next.js Projects

Признаки:

- зависимость `next`;
- `app/` или `pages/`;
- `next.config.js` или `next.config.ts`.

Что важно понять:

- используется ли App Router или Pages Router;
- есть ли серверные компоненты;
- где API routes;
- как устроены env-переменные;
- есть ли middleware и специальные настройки для deploy.

При анализе задач:

- проблемы сборки часто связаны с импортами, env, server/client boundaries;
- проблемы рантайма часто связаны с data fetching, route params и SSR;
- проблемы деплоя часто связаны с output, env и build command.

Порядок работы:

1. Определи router.
2. Найди затронутый route или component.
3. Проверь `package.json`, `next.config.*`, env-файлы и ошибку сборки.
4. Исправь минимально.
5. Подтверди через `build` или другой релевантный чек.
