/**
 * YOLO-Forge SP — Electron Bootstrap
 * 
 * This is the entry point referenced by package.json "main".
 * It registers ts-node so that all subsequent require() calls
 * for .ts files are handled automatically — no pre-compilation needed.
 */

const path = require('path');

// Register ts-node to handle TypeScript imports on-the-fly
try {
  require('ts-node').register({
    project: path.join(__dirname, '..', 'tsconfig.electron.json'),
    transpileOnly: true,  // Skip type checking for faster startup
    compilerOptions: {
      module: 'commonjs',
      target: 'ES2022',
      esModuleInterop: true,
    },
  });
} catch (err) {
  console.error('Failed to register ts-node. Did you run npm install?');
  console.error(err);
  process.exit(1);
}

// Now load the actual main process (TypeScript)
require('./main');
