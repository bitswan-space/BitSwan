/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1c1917',
          dark: '#FAFAF9',
          light: '#1c1917',
        },
        secondary: {
          DEFAULT: '#CBCACA',
          dark: '#2D2D2D',
          light: '#CBCACA',
        },
        neutral: {
          DEFAULT: '#FAFAF9',
          light: '#FAFAF9',
          dark: '#424242',
        }
      },
    },
  },
  plugins: [],
}
