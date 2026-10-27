const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const ROOT = resolve(__dirname, '..');
const BASE_JS = readFileSync(resolve(ROOT, 'static/js/base.js'), 'utf8');

// Templates that make up the authenticated workspace. They all share the sidebar and must
// render it exactly once inside an app shell.
const WORKSPACE_PAGES = [
    'dashboard.html',
    'profile.html',
    'question_bank.html',
    'admin_panel.html',
    'classes.html',
    'class_detail.html',
    'quiz_builder.html',
    'notifications.html',
];

// Pages that intentionally keep the full-width layout (auth, marketing, exam taking).
const FULL_WIDTH_PAGES = ['login.html', 'register.html', 'home.html', 'quiz_taker.html'];

const SIDEBAR_INCLUDE = /{%\s*include 'components\/app_sidebar\.html'\s*%}/g;

function fakeElement(dataset = {}, hidden = false) {
    const attributes = new Map();
    const classes = new Set();
    return {
        dataset,
        hidden,
        classList: {
            add(name) { classes.add(name); },
            toggle(name, on) { on ? classes.add(name) : classes.delete(name); },
            contains(name) { return classes.has(name); },
        },
        setAttribute(name, value) { attributes.set(name, value); },
        removeAttribute(name) { attributes.delete(name); },
        getAttribute(name) { return attributes.has(name) ? attributes.get(name) : null; },
    };
}

function createContext({ pathname = '/dashboard/' } = {}) {
    const navAuth = { innerHTML: '' };
    const shell = fakeElement();
    const links = {
        dashboard: fakeElement({ nav: 'dashboard' }),
        questionBank: fakeElement({ nav: 'question-bank', teacherOnly: '' }, true),
        admin: fakeElement({ nav: 'admin', adminOnly: '' }, true),
    };
    const navLinks = Object.values(links);
    const sidebar = {
        hidden: true,
        querySelectorAll(selector) {
            if (selector === '[data-nav]') return navLinks;
            if (selector === '[data-admin-only]') return navLinks.filter(el => 'adminOnly' in el.dataset);
            if (selector === '[data-teacher-only]') return navLinks.filter(el => 'teacherOnly' in el.dataset);
            return [];
        },
    };

    const context = vm.createContext({
        console,
        document: {
            getElementById(id) {
                if (id === 'navAuthLinks') return navAuth;
                if (id === 'appSidebar') return sidebar;
                return null;
            },
            querySelector(selector) { return selector === '.app-shell' ? shell : null; },
            querySelectorAll() { return []; },
            addEventListener() {},
        },
        localStorage: { getItem: () => null, removeItem() {}, setItem() {} },
        fetch: async () => new Response('{}', { status: 200 }),
        addEventListener() {},
        setTimeout,
        setInterval() { return 0; },
        clearInterval() {},
        Request,
        Response,
        URLSearchParams,
    });
    context.window = context;
    context.location = { pathname, replace() {} };

    vm.runInContext(BASE_JS, context);
    return { context, navAuth, shell, sidebar, links };
}

function makeUser(role) {
    return {
        username: `${role}_user`,
        first_name: 'Test',
        last_name: 'User',
        role: { name: role },
    };
}

const NAVBAR_WORKSPACE_LINKS = [
    /href="\/dashboard\/"/,
    /href="\/classes\/"/,
    /\/exams\/question-bank\//,
    /\/admin-panel\//,
];

for (const role of ['student', 'teacher']) {
    test(`navbar shows only account actions for ${role}`, () => {
        const { context, navAuth } = createContext({ pathname: '/classes/' });

        context.updateNavbarUI(makeUser(role));

        for (const pattern of NAVBAR_WORKSPACE_LINKS) {
            assert.doesNotMatch(navAuth.innerHTML, pattern);
        }
        assert.match(navAuth.innerHTML, /id="navBellBtn"/);
        assert.match(navAuth.innerHTML, /href="\/profile\/"/);
        assert.match(navAuth.innerHTML, /doLogout\(\)/);
    });
}

test('navbar leaves navigation to the sidebar even on pages without a shell', () => {
    const { context, navAuth } = createContext({ pathname: '/exams/question-bank/' });

    context.updateNavbarUI(makeUser('teacher'));

    assert.doesNotMatch(navAuth.innerHTML, /nav-btn-solid/);
    assert.match(navAuth.innerHTML, /id="navBellBtn"/);
});

test('sidebar shows the dashboard link for every authenticated role', () => {
    for (const role of ['student', 'teacher', 'admin']) {
        const { context, shell, sidebar, links } = createContext();

        context.updateAppShell(makeUser(role));

        assert.equal(sidebar.hidden, false, `${role} should see the sidebar`);
        assert.equal(shell.classList.contains('has-sidebar'), true);
        assert.equal(links.dashboard.hidden, false);
    }
});

test('sidebar hides staff-only links from students', () => {
    const { context, sidebar, links } = createContext();

    context.updateAppShell(makeUser('student'));

    assert.equal(sidebar.hidden, false);
    assert.equal(links.questionBank.hidden, true);
    assert.equal(links.admin.hidden, true);
});

test('sidebar shows question bank to teachers but keeps admin hidden', () => {
    const { context, links } = createContext();

    context.updateAppShell(makeUser('teacher'));

    assert.equal(links.questionBank.hidden, false);
    assert.equal(links.admin.hidden, true);
});

test('sidebar shows every link to admins', () => {
    const { context, links } = createContext();

    context.updateAppShell(makeUser('admin'));

    assert.equal(links.questionBank.hidden, false);
    assert.equal(links.admin.hidden, false);
});

for (const [pathname, active] of [
    ['/dashboard/', 'dashboard'],
    ['/dashboard', 'dashboard'],
    ['/exams/question-bank/', 'question-bank'],
    ['/admin-panel/', 'admin'],
    ['/classes/', ''],
]) {
    test(`sidebar marks "${active || 'none'}" active on ${pathname}`, () => {
        const { context, links } = createContext({ pathname });

        context.updateAppShell(makeUser('admin'));

        for (const [key, element] of Object.entries(links)) {
            const shouldBeActive = element.dataset.nav === active;
            assert.equal(
                element.classList.contains('is-active'),
                shouldBeActive,
                `${key} active state on ${pathname}`,
            );
            assert.equal(element.getAttribute('aria-current'), shouldBeActive ? 'page' : null);
        }
    });
}

for (const page of WORKSPACE_PAGES) {
    test(`${page} renders the shared sidebar inside the app shell`, () => {
        const html = readFileSync(resolve(ROOT, 'templates', page), 'utf8');

        assert.match(html, /class="app-shell"/);
        assert.equal((html.match(/class="app-main"/g) || []).length, 1);
        assert.equal((html.match(SIDEBAR_INCLUDE) || []).length, 1);
    });
}

for (const page of FULL_WIDTH_PAGES) {
    test(`${page} stays full width without the sidebar`, () => {
        const html = readFileSync(resolve(ROOT, 'templates', page), 'utf8');

        assert.doesNotMatch(html, /class="app-shell"/);
        assert.equal((html.match(SIDEBAR_INCLUDE) || []).length, 0);
    });
}

test('sidebar gates staff links by role attribute', () => {
    const html = readFileSync(resolve(ROOT, 'templates/components/app_sidebar.html'), 'utf8');

    assert.match(
        html,
        /href="\/exams\/question-bank\/"[^>]*data-teacher-only/,
        'question bank must only render for teachers/admins',
    );
    assert.match(
        html,
        /href="\/admin-panel\/"[^>]*data-admin-only/,
        'admin panel must only render for admins',
    );
});
