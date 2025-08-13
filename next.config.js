/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",

  webpack: (config, { isServer }) => {
    // Add a rule to handle .mjs files
    config.module.rules.push({
      test: /\.mjs$/,
      include: /node_modules/,
      type: "javascript/auto",
    });

    return config;
  },

  // Removed output: "export" to allow dynamic API routes
  // Re-writes dont work with Tauri...since output above is set to "export"
  // rewrites: async () => {
  //   return [
  //     {
  //       source: "/api/v1/text/:path*",
  //       destination:
  //         process.env.NODE_ENV === "development"
  //           ? "http://127.0.0.1:8008/api/v1/text/:path*"
  //           : "/api/v1/text/:path*",
  //     },
  //   ];
  // },
};

// Integrate next-intl plugin and point to the request config module
const withNextIntl = require('next-intl/plugin')('./i18n/request.ts');

module.exports = withNextIntl(nextConfig);
