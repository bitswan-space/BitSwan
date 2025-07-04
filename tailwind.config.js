/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './bspump/**/*.py',
    './bspump/**/*.js',
    './bspump/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1c1917',
          dark: '#FAFAF9',
          light: '#1c1917',
        },
        secondary: {
          DEFAULT: '#E6E6E6',
          dark: '#2D2D2D',
          light: '#E6E6E6',
        },
        neutral: {
          DEFAULT: '#FAFAF9',
          light: '#FAFAF9',
          dark: '#424242',
        }
      },
    },
  },
  plugins: [
    require('tailwindcss'),
    require('autoprefixer'),
  ]
};


