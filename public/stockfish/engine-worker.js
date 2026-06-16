/* global Stockfish */

const ENGINE_INIT_TIMEOUT_MS = 10000;
const SEARCH_TIMEOUT_MS = 30000;

let enginePromise = null;
let engine = null;
let uciReady = false;
let activeJob = null;
let activeTimer = null;
let initTimer = null;
let initReject = null;

function sendToMain(payload) {
  self.postMessage(payload);
}

function failActiveJob(message) {
  if (!activeJob) return;
  const jobId = activeJob.jobId;
  activeJob = null;
  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }
  sendToMain({ jobId, error: message });
}

function handleEngineLine(rawLine) {
  const line = String(rawLine).trim();
  if (!line) return;

  if (line === 'uciok') {
    uciReady = true;
    if (initTimer) {
      clearTimeout(initTimer);
      initTimer = null;
    }
    initReject = null;
    return;
  }

  if (!line.startsWith('bestmove ')) return;

  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }

  const job = activeJob;
  activeJob = null;
  if (!job) return;

  const move = line.split(/\s+/)[1] ?? '';
  if (!move || move === '(none)' || move === 'none') {
    sendToMain({ jobId: job.jobId, error: 'AI 没有找到合法走法' });
    return;
  }

  sendToMain({
    jobId: job.jobId,
    result: {
      move,
      depth: job.depth,
      timeUsed: Math.round(performance.now() - job.startedAt),
    },
  });
}

async function ensureEngine() {
  if (engine && uciReady) return engine;
  if (enginePromise) return enginePromise;

  enginePromise = new Promise((resolve, reject) => {
    initReject = reject;
    initTimer = setTimeout(() => {
      initTimer = null;
      reject(new Error('AI 引擎初始化超时'));
    }, ENGINE_INIT_TIMEOUT_MS);

    importScripts('./stockfish.js');

    Stockfish({
      locateFile: (file) => `/stockfish/${file}`,
      mainScriptUrlOrBlob: '/stockfish/stockfish.js',
    }).then((instance) => {
      engine = instance;
      engine.addMessageListener(handleEngineLine);
      engine.postMessage('uci');

      const waitForUci = () => {
        if (uciReady) {
          engine.postMessage('setoption name UCI_Variant value xiangqi');
          engine.postMessage('ucinewgame');
          resolve(engine);
          return;
        }
        setTimeout(waitForUci, 20);
      };
      waitForUci();
    }).catch((error) => {
      if (initTimer) {
        clearTimeout(initTimer);
        initTimer = null;
      }
      reject(error);
    });
  }).catch((error) => {
    enginePromise = null;
    if (initReject) {
      initReject = null;
    }
    throw error;
  });

  return enginePromise;
}

self.addEventListener('message', async (event) => {
  const { jobId, options } = event.data;
  const fen = options?.fen;
  const depth = Number(options?.depth ?? 4);

  if (!jobId) {
    sendToMain({ jobId: '', error: 'AI 请求缺少 jobId' });
    return;
  }

  if (!fen) {
    sendToMain({ jobId, error: 'AI 请求缺少 FEN' });
    return;
  }

  try {
    const sf = await ensureEngine();

    if (activeJob) {
      sf.postMessage('stop');
      failActiveJob('AI 搜索被新的请求中断');
    }

    activeJob = {
      jobId,
      depth,
      startedAt: performance.now(),
    };

    activeTimer = setTimeout(() => {
      sf.postMessage('stop');
      failActiveJob('AI 搜索超时');
    }, SEARCH_TIMEOUT_MS);

    sf.postMessage('ucinewgame');
    sf.postMessage(`position fen ${fen}`);
    sf.postMessage(`go depth ${depth}`);
  } catch (error) {
    sendToMain({
      jobId,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});
