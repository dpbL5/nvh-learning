const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

test('true/false submission keeps the Đúng/Sai value for every statement', async () => {
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
            if (url === '/api/exams/1/') return new Promise(() => {});
            requests.push(new Request('https://example.test' + url, init));
            return new Response('{}', { status: 200 });
        },
    });
    context.window = context;

    for (const file of ['quiz_taker.js', 'base.js']) {
        vm.runInContext(readFileSync(resolve(__dirname, '../static/js', file), 'utf8'), context);
    }

    vm.runInContext(`
        attemptId = 9;
        quizQuestions = [{id: 3, question: {question_type: 'true_false'}}];
        currentAnswers = {3: {true_false_answers: {11: true, 12: false}}};
        showResult = function() {};
    `, context);

    await context.submitExam(false);

    assert.equal(requests.length, 1);
    assert.deepEqual(await requests[0].json(), {
        answers: [
            { quiz_question_id: 3, selected_option_id: 11, answer_value: true },
            { quiz_question_id: 3, selected_option_id: 12, answer_value: false },
        ],
    });
});
