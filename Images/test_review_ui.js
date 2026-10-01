const assert = require('node:assert/strict');
const vm = require('node:vm');
let keydown, posted;
const elements = {};
function element() {
  return {innerHTML: '', textContent: '', value: '', style: {}, focus() {},
          appendChild() {}, querySelector() { return null; }};
}
const ctx = vm.createContext({
  console,
  document: {
    getElementById(id) { return elements[id] ||= element(); },
    createElement: element,
    createTextNode(text) { return {textContent: text}; },
    addEventListener(name, callback) { if (name === 'keydown') keydown = callback; }
  },
  async fetch(url, options) {
    posted = JSON.parse(options.body);
    return {async json() { return {ok: true, correction: {correct: posted.correct}, revision: 'new'}; }};
  }
});
/* APP_SCRIPT */
const run = code => vm.runInContext(code, ctx);
run(`
  defs = {primary_subject: {human:'human', robot:'robot', android:'android',
          multiple:'multiple', none:'none'},
          representation: {photograph:'photo', illustration:'art',
          statue_or_render:'statue', text_screenshot:'screen', other:'other'}};
  records = [{
    file:'image_01.jpg', revision:'old', description:'Robot with a background person.',
    queued:true, queued_reason:'text_bearing', reviewed:false, correction:null,
    facets: {
      contains_human:{choice:'yes',confidence:1},
      contains_robot:{choice:'yes',confidence:1},
      contains_android:{choice:'no',confidence:1},
      primary_subject:{choice:'robot',confidence:1},
      representation:{choice:'photograph',confidence:1}
    }
  }];
  rebuild();
`);
assert.equal(run('pick.flags.contains_human'), true);
assert.equal(run('pick.flags.contains_robot'), true);
elements.note.value = 'Keep this note';
keydown({target:{tagName:'BODY'}, key:'1'});
assert.equal(run('pick.subject'), 'human');
assert.equal(run('pick.flags.contains_robot'), true);
keydown({target:{tagName:'BODY'}, key:'w'});
assert.equal(run('pick.rep'), 'illustration');
assert.equal(elements.note.value, 'Keep this note');
run('save()').then(() => {
  assert.equal(posted.revision, 'old');
  assert.equal(posted.correct.contains_human, 'yes');
  assert.equal(posted.correct.contains_robot, 'yes');
  assert.equal(posted.correct.representation, 'illustration');
  assert.equal(run('order.length'), 0);
  assert.match(elements.pane.innerHTML, /Review complete/);
}).catch(error => { console.error(error); process.exitCode = 1; });
