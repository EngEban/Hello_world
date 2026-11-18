import hooks from 'eslint-plugin-react-hooks';
import react from 'eslint-plugin-react';
import globals from 'globals';
export default [{ files:['src/**/*.{js,jsx}'], ignores:['src/data/journalFinder/journals_db.js'],
 languageOptions:{ ecmaVersion:'latest', sourceType:'module', globals:{...globals.browser}, parserOptions:{ecmaFeatures:{jsx:true}} },
 plugins:{ 'react-hooks':hooks, react }, settings:{react:{version:'18.3'}},
 rules:{ 'react-hooks/rules-of-hooks':'error','react-hooks/exhaustive-deps':'warn','no-undef':'error','no-unused-vars':['warn',{varsIgnorePattern:'^(React|_)',ignoreRestSiblings:true}],'react/jsx-uses-vars':'error','react/jsx-uses-react':'error','react/jsx-key':'error','react/jsx-no-target-blank':'warn' } }];
