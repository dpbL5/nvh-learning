const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

for (const [name, isAuto, expired] of [
    ['manual submission', false, false],
    ['timed submission', true, false],
    ['submission after token refresh', false, true],
]) {
    test(name + ' sends JSON after base.js loads', async () => {
        const requests = [];
        const context = vm.createContext({
            quizId: 1,
            localStorage: { getItem: () => '1', removeItem() {} },
            document: { getElementById: () => ({}), addEventListener() {} },
            addEventListener() {},
            bootstrap: { Modal: { getInstance: () => null } },
            clearInterval() {},
            alert(message) { assert.fail(message); },
            fetch: async (url, init) => {
                // Leave page initialization pending; exercise submission independently.
                if (url === '/api/exams/1/') return new Promise(() => {});
                requests.push(new Request('https://example.test' + url, init));
                const status = expired && requests.length === 1 ? 401 : 200;
                return new Response('{}', { status });
            },
        });
        context.window = context;
        // Match quiz_taker.html's content script followed by base.html's shared script.
        for (const file of ['quiz_taker.js', 'base.js']) {
            vm.runInContext(readFileSync(resolve(__dirname, '../static/js', file), 'utf8'), context);
        }
        vm.runInContext(`
            attemptId = 42;
            quizQuestions = [{id: 3, question: {question_type: 'multiple_choice'}}];
            currentAnswers = {3: {selected_option_id: 7}};
            showResult = function() {};
        `, context);

        await context.submitExam(isAuto);

        assert.equal(requests.length, expired ? 3 : 1);
        for (const request of requests.filter(r => r.url.endsWith('/submit/'))) {
            assert.equal(request.method, 'POST');
            assert.equal(request.headers.get('Content-Type'), 'application/json');
            assert.deepEqual(await request.json(), {
                answers: [{ quiz_question_id: 3, selected_option_id: 7 }],
            });
        }
    });
}
