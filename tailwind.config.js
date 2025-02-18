/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './bspump/**/*.py',
    './bspump/**/*.js',
    './bspump/**/*.html',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('tailwindcss'),
    require('autoprefixer'),
  ]
};


