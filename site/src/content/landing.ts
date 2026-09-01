/**
 * Copy for the two landing pages.
 *
 * Both languages share one shape so a change to the page cannot land in only
 * one of them: the type below is what Landing.astro renders, and TypeScript
 * requires every locale to fill it in.
 */

export type Feature = {
  title: string;
  body: string;
  href: string;
};

export type Step = {
  label: string;
  command: string;
  note: string;
};

export type Link = {
  label: string;
  href: string;
};

export type LandingCopy = {
  lang: string;
  htmlLang: string;
  tagline: string;
  summary: string;
  /** Top bar links. The docs entry points at the first page, because the
   *  locale root serves the landing page rather than a docs index. */
  nav: Link[];
  primaryCta: Link;
  secondaryCta: Link;
  otherLanguage: Link;
  castCaption: string;
  castAlt: string;
  installHeading: string;
  installNote: string;
  steps: Step[];
  featureHeading: string;
  features: Feature[];
  demoHeading: string;
  demoBody: string;
  demoCta: string;
  demoNote: string;
  docsHeading: string;
  docsBody: string;
  docsCta: string;
  footerNote: string;
};

export const zh: LandingCopy = {
  lang: 'zh',
  htmlLang: 'zh-CN',
  tagline: 'macOS 上的本地服务与 SSH 控制台',
  summary:
    '把每个本地服务写成一条命令模板，LocalSM 接管端口、日志、进程生命周期、' +
    '远端监听扫描和 SSH 隧道。没有常驻 supervisor：LocalSM 退出，服务照旧运行。',
  nav: [
    { label: '文档', href: 'zh/install/' },
    { label: '仿真面板', href: 'demo/' },
    { label: 'CLI 参考', href: 'zh/cli-reference/' },
  ],
  primaryCta: { label: '快速上手', href: 'zh/quickstart/' },
  secondaryCta: { label: '看看面板', href: 'demo/' },
  otherLanguage: { label: 'English', href: 'en/' },
  castCaption: '真实终端录制，和仿真面板用的是同一套演示服务。',
  castAlt: '终端录屏：LocalSM status 列出四个服务，up api 启动其中一个，logs 与 --json status 显示它的输出。',
  installHeading: '装上它',
  installNote: 'npm 包内置匹配版本的 wheel，首次运行会在缺少 uv 时自动装好它。',
  steps: [
    {
      label: '安装并生成配置',
      command: 'npx @shendeguize/local-sm init',
      note: '在 ~/.config/localsm/ 写入带注释的模板，不覆盖任何已有文件。',
    },
    {
      label: '描述你的服务',
      command: 'LocalSM edit',
      note: '用 $EDITOR 打开配置，退出后告诉你哪些服务需要重启。',
    },
    {
      label: '跑起来',
      command: 'LocalSM up && LocalSM web',
      note: '启动全部服务，并在 127.0.0.1:8765 打开操作台。',
    },
  ],
  featureHeading: '它替你记住的事',
  features: [
    {
      title: '端口有记性',
      body:
        '每个服务上次成功用的端口会被记下来，重启通常回到同一个地址，' +
        '所以你收藏的链接不会失效。冲突时用 --auto-port 从池里换一个。',
      href: 'zh/services/',
    },
    {
      title: '开机自启是按服务选的',
      body:
        'enable 把单个服务交给 launchd，登录即起、崩溃自愈，端口在那一刻' +
        '冻结进 plist——launchd 拉起服务时没有 CLI 在场去协商端口。',
      href: 'zh/launchd/',
    },
    {
      title: '远端有什么在听',
      body:
        '并行扫描 ~/.ssh/config 里的主机，探测命令从 ss 一路降级到读 ' +
        '/proc/net/tcp，精简容器里也能用，并标出哪些端口还没被隧道覆盖。',
      href: 'zh/remote/',
    },
    {
      title: '隧道会自己回来',
      body:
        'ExitOnForwardFailure 让绑不上端口的 ssh 直接退出，而不是留一个' +
        '假装在工作的连接；tunnel ensure 只重建真正死掉的那几条。',
      href: 'zh/tunnels/',
    },
    {
      title: '面板只回应本机',
      body:
        '永久 localhost 零鉴权，外加 Host 头校验——它封的是 DNS rebinding：' +
        '一个解析到 127.0.0.1 的攻击者域名，本来能借你的浏览器调这套 API。',
      href: 'zh/web/',
    },
    {
      title: '脚本有稳定契约',
      body:
        '每条命令都有 --json 和约定好的退出码，补全脚本和 CLI 参考都由 ' +
        'parser 自动生成，不会和实际行为脱节。',
      href: 'zh/cli-contract/',
    },
  ],
  demoHeading: '不装也能看',
  demoBody:
    '仿真面板跑的是真实前端代码，只把 HTTP 层换成浏览器里的内存状态机。' +
    '启停、改端口、扫描、建隧道都会真的改变状态，刷新页面复位。',
  demoCta: '打开仿真面板',
  demoNote: '数据是演示用的假服务和假主机，不会碰你的机器。',
  docsHeading: '读文档',
  docsBody:
    '安装、配置、服务、launchd、隧道、远端扫描、面板、CLI 参考与故障排查，' +
    '中英双语。中文是源，英文一一对应。',
  docsCta: '进入文档',
  footerNote: '仅支持 macOS。MIT 许可。',
};

export const en: LandingCopy = {
  lang: 'en',
  htmlLang: 'en',
  tagline: 'A console for local services and SSH on macOS',
  summary:
    'Write each local service down as one command template, and LocalSM takes ' +
    'over ports, logs, process lifecycle, remote listener scans, and SSH ' +
    'tunnels. There is no resident supervisor: LocalSM exits, services keep running.',
  nav: [
    { label: 'Docs', href: 'en/install/' },
    { label: 'Demo', href: 'demo/' },
    { label: 'CLI reference', href: 'en/cli-reference/' },
  ],
  primaryCta: { label: 'Quickstart', href: 'en/quickstart/' },
  secondaryCta: { label: 'See the dashboard', href: 'demo/' },
  otherLanguage: { label: '简体中文', href: '' },
  castCaption: 'A real terminal recording, driving the same demo services as the simulated dashboard.',
  castAlt:
    'Terminal recording: LocalSM status lists four services, up api starts one of them, and logs and --json status show its output.',
  installHeading: 'Install it',
  installNote:
    'The npm package bundles a matching wheel, and installs uv on first run when it is missing.',
  steps: [
    {
      label: 'Install and write the config',
      command: 'npx @shendeguize/local-sm init',
      note: 'Writes commented templates to ~/.config/localsm/, overwriting nothing.',
    },
    {
      label: 'Describe your services',
      command: 'LocalSM edit',
      note: 'Opens the config in $EDITOR and reports which services need a restart.',
    },
    {
      label: 'Run them',
      command: 'LocalSM up && LocalSM web',
      note: 'Starts every service and opens the console on 127.0.0.1:8765.',
    },
  ],
  featureHeading: 'What it remembers for you',
  features: [
    {
      title: 'Ports are sticky',
      body:
        'The port each service last used successfully is recorded, so a restart ' +
        'usually lands on the same address and your bookmarks keep working. ' +
        'Pass --auto-port to take a different one from the pool on a conflict.',
      href: 'en/services/',
    },
    {
      title: 'Start at login, per service',
      body:
        'enable hands one service to launchd for start-at-login and crash ' +
        'recovery, freezing the port into the plist at that moment: launchd ' +
        'starts the service with no CLI present to negotiate one.',
      href: 'en/launchd/',
    },
    {
      title: 'What is listening out there',
      body:
        'Scans the hosts in ~/.ssh/config in parallel, degrading from ss all ' +
        'the way down to reading /proc/net/tcp so stripped containers still ' +
        'answer, and marks the ports no tunnel covers.',
      href: 'en/remote/',
    },
    {
      title: 'Tunnels come back',
      body:
        'ExitOnForwardFailure makes an ssh that cannot bind its port exit ' +
        'rather than linger pretending to work, and tunnel ensure rebuilds ' +
        'only the ones that actually died.',
      href: 'en/tunnels/',
    },
    {
      title: 'The dashboard answers loopback only',
      body:
        'Permanently localhost with no login, plus Host header validation, ' +
        'which is what closes DNS rebinding: an attacker domain resolving to ' +
        '127.0.0.1 could otherwise drive this API through your browser.',
      href: 'en/web/',
    },
    {
      title: 'A stable contract for scripts',
      body:
        'Every command has --json and a defined exit code, and both the ' +
        'completion scripts and the CLI reference are generated from the ' +
        'parser so they cannot drift from the real behaviour.',
      href: 'en/cli-contract/',
    },
  ],
  demoHeading: 'Look before installing',
  demoBody:
    'The simulated dashboard runs the real front-end code with only the HTTP ' +
    'layer swapped for an in-memory state machine in your browser. Starting, ' +
    'stopping, changing ports, scanning, and creating tunnels all really change ' +
    'state; a refresh resets it.',
  demoCta: 'Open the simulated dashboard',
  demoNote: 'The data is made-up services and hosts. Nothing touches your machine.',
  docsHeading: 'Read the docs',
  docsBody:
    'Installation, configuration, services, launchd, tunnels, remote scans, the ' +
    'dashboard, the CLI reference, and troubleshooting, in both languages. ' +
    'Chinese is the source and English mirrors it page for page.',
  docsCta: 'Go to the docs',
  footerNote: 'macOS only. MIT licensed.',
};
