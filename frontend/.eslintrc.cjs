module.exports = {
  root: true,
  env: { browser: true, es2023: true },
  extends: [
    "airbnb",
    "airbnb/hooks",
    "airbnb-typescript",
    "plugin:react/jsx-runtime",
    "plugin:@typescript-eslint/recommended",
    "plugin:import/recommended",
    "plugin:import/typescript",
    "prettier",
  ],
  parserOptions: {
    project: ["./tsconfig.json"],
    tsconfigRootDir: __dirname,
  },
  rules: {
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "import/prefer-default-export": "off",
    "react/jsx-props-no-spreading": "off",
  },
  settings: {
    react: {
      version: "detect",
    },
  },
};

