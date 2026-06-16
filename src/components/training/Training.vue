<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue';
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NTag,
} from 'naive-ui';
import RecognizeCorners from '@/components/editor/RecognizeCorners.vue';
import {
  checkModel,
  extractTrainingCrops,
  generateTrainingData,
  getTrainingStatus,
  trainModel,
  type TrainingStatus,
} from '@/utils/training-api';

const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = shallowRef<File | null>(null);
const showCornerPicker = ref(false);
const fen = ref('');
const corners = ref('');
const error = ref('');
const status = ref<TrainingStatus>({
  running: false,
  phase: 'idle',
  ok: true,
  message: '',
  logs: [],
  updated_at: 0,
});

const dataOptions = reactive({
  per_class: 1000,
  val_frac: 0.15,
  real_repeat: 8,
  clean: true,
});

const trainOptions = reactive({
  epochs: 20,
  batch: 128,
  lr: 0.001,
  export_only: false,
});

let pollTimer: number | null = null;

const selectedFileLabel = computed(() => selectedFile.value?.name ?? '未选择截图');
const statusType = computed<'success' | 'error' | 'info' | 'warning'>(() => {
  if (status.value.running) return 'info';
  return status.value.ok ? 'success' : 'error';
});
const phaseLabel = computed(() => {
  const map: Record<string, string> = {
    idle: '空闲',
    busy: '忙碌',
    'extract-crops': '提取 crops',
    'generate-data': '生成训练集',
    'train-model': '训练模型',
    'check-model': '检查模型',
  };
  return map[status.value.phase] ?? status.value.phase;
});
const canExtract = computed(() =>
  Boolean(selectedFile.value && fen.value.trim() && corners.value.trim()) && !status.value.running,
);
const logsText = computed(() => status.value.logs.join('\n'));

function pickImage() {
  error.value = '';
  fileInput.value?.click();
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  input.value = '';
  corners.value = '';
}

function openCorners() {
  if (!selectedFile.value) {
    error.value = '请先选择一张真实残局截图。';
    return;
  }
  isEnter.value = false;
  showCornerPicker.value = true;
}

function onCornerConfirm(value: string) {
  corners.value = value;
  showCornerPicker.value = false;
  isEnter.value = false;
}

function onCornerCancel() {
  showCornerPicker.value = false;
  isEnter.value = false;
}

function onCornerAuto() {
  showCornerPicker.value = false;
  error.value = '提取训练 crops 需要准确四角，请手动拖动四角点后确认。';
}

async function refreshStatus() {
  try {
    status.value = await getTrainingStatus();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法连接训练服务。';
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = window.setInterval(async () => {
    await refreshStatus();
    if (!status.value.running) {
      stopPolling();
    }
  }, 1000);
}

function stopPolling() {
  if (!pollTimer) return;
  window.clearInterval(pollTimer);
  pollTimer = null;
}

async function runTask(task: () => Promise<TrainingStatus>) {
  error.value = '';
  try {
    status.value = await task();
    startPolling();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '训练任务启动失败。';
  }
}

function runExtractCrops() {
  const file = selectedFile.value;
  if (!file) return;
  runTask(() => extractTrainingCrops(file, {
    fen: fen.value.trim(),
    corners: corners.value.trim() || undefined,
  }));
}

function runGenerateData() {
  runTask(() => generateTrainingData({
    per_class: dataOptions.per_class,
    val_frac: dataOptions.val_frac,
    real_repeat: dataOptions.real_repeat,
    clean: dataOptions.clean,
  }));
}

function runTrainModel() {
  runTask(() => trainModel({
    epochs: trainOptions.epochs,
    batch: trainOptions.batch,
    lr: trainOptions.lr,
    export_only: trainOptions.export_only,
  }));
}

function runCheckModel() {
  runTask(() => checkModel('val'));
}

onBeforeUnmount(() => {
  stopPolling();
});

onMounted(async () => {
  await refreshStatus();
  if (status.value.running) {
    startPolling();
  }
});

const isEnter = ref(false);
function onAfterEnter() {
  isEnter.value = true;
}
</script>

<template>
  <div class="training-layout">
    <section class="training-main">
      <NCard title="1. 收集真实 crops" size="small">
        <NSpace vertical size="medium">
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            class="hidden-input"
            @change="onFileChange"
          />
          <div class="file-row">
            <NButton size="small" @click="pickImage">选择真实截图</NButton>
            <NTag :bordered="false" type="info">{{ selectedFileLabel }}</NTag>
          </div>
          <NInput
            v-model:value="fen"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
            placeholder="粘贴这张截图对应的正确 FEN"
          />
          <div class="corners-row">
            <NButton size="small" :disabled="!selectedFile" @click="openCorners">框选四角</NButton>
            <NInput
              v-model:value="corners"
              size="small"
              placeholder="必填：x0,y0;x1,y1;x2,y2;x3,y3"
            />
          </div>
          <NAlert v-if="selectedFile && fen.trim() && !corners.trim()" type="warning" :show-icon="false">
            提取 crops 需要手动框选四角，自动定位在真实截图上容易失败。
          </NAlert>
          <NButton type="primary" :disabled="!canExtract" :loading="status.running && status.phase === 'extract-crops'" @click="runExtractCrops">
            提取 crops
          </NButton>
        </NSpace>
      </NCard>

      <NCard title="2. 生成训练集" size="small">
        <div class="field-grid">
          <label>
            <span>每类合成样本</span>
            <NInputNumber v-model:value="dataOptions.per_class" :min="100" :step="100" />
          </label>
          <label>
            <span>验证集比例</span>
            <NInputNumber v-model:value="dataOptions.val_frac" :min="0.05" :max="0.4" :step="0.01" />
          </label>
          <label>
            <span>真实裁剪增强次数</span>
            <NInputNumber v-model:value="dataOptions.real_repeat" :min="1" :step="1" />
          </label>
          <label class="check-field">
            <NCheckbox v-model:checked="dataOptions.clean">重新生成前清空 dataset</NCheckbox>
          </label>
        </div>
        <NButton type="primary" :disabled="status.running" :loading="status.running && status.phase === 'generate-data'" @click="runGenerateData">
          生成 dataset
        </NButton>
      </NCard>

      <NCard title="3. 训练与检查" size="small">
        <div class="field-grid">
          <label>
            <span>训练轮数</span>
            <NInputNumber v-model:value="trainOptions.epochs" :min="1" :step="1" />
          </label>
          <label>
            <span>Batch</span>
            <NInputNumber v-model:value="trainOptions.batch" :min="16" :step="16" />
          </label>
          <label>
            <span>学习率</span>
            <NInputNumber v-model:value="trainOptions.lr" :min="0.0001" :step="0.0001" />
          </label>
          <label class="check-field">
            <NCheckbox v-model:checked="trainOptions.export_only">只从 checkpoint 导出 ONNX</NCheckbox>
          </label>
        </div>
        <NSpace>
          <NButton type="primary" :disabled="status.running" :loading="status.running && status.phase === 'train-model'" @click="runTrainModel">
            {{ trainOptions.export_only ? '导出 ONNX' : '开始训练' }}
          </NButton>
          <NButton :disabled="status.running" :loading="status.running && status.phase === 'check-model'" @click="runCheckModel">
            检查模型
          </NButton>
        </NSpace>
      </NCard>
    </section>

    <aside class="training-side">
      <NCard title="任务状态" size="small">
        <NSpace vertical>
          <NTag :bordered="false" :type="statusType">
            {{ status.running ? '运行中' : '已停止' }} · {{ phaseLabel }}
          </NTag>
          <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
          <NAlert v-else-if="status.message" :type="status.ok ? 'success' : 'error'" :show-icon="false">
            {{ status.message }}
          </NAlert>
          <pre class="logs">{{ logsText || '暂无日志' }}</pre>
        </NSpace>
      </NCard>
    </aside>

    <NModal
      v-model:show="showCornerPicker"
      preset="card"
      title="框选训练截图四角"
      style="width: min(96vw, 1280px); max-height: min(94vh, 920px)"
      class="corner-modal"
      :mask-closable="false"
      @after-enter="onAfterEnter"
      @before-leave="isEnter = false"
    >
      <RecognizeCorners
        v-if="selectedFile"
        :file="selectedFile"
        :show-auto="false"
        :is-enter="isEnter"
        @confirm="onCornerConfirm"
        @auto="onCornerAuto"
        @cancel="onCornerCancel"
      />
    </NModal>
  </div>
</template>

<style scoped>
.training-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
  gap: 18px;
  align-items: start;
}

.training-main {
  display: grid;
  gap: 14px;
}

.training-side {
  position: sticky;
  top: 16px;
}

.hidden-input {
  display: none;
}

.file-row,
.corners-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.corners-row {
  align-items: stretch;
}

.corners-row :deep(.n-input) {
  flex: 1;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.field-grid label {
  display: grid;
  gap: 6px;
}

.field-grid span {
  color: #d8c4a2;
  font-size: 12px;
}

.check-field {
  align-content: end;
}

.logs {
  min-height: 360px;
  max-height: 520px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid rgba(236, 202, 142, 0.16);
  border-radius: 8px;
  background: rgba(8, 6, 5, 0.5);
  color: #d8c4a2;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
}

@media (max-width: 980px) {
  .training-layout,
  .field-grid {
    grid-template-columns: 1fr;
  }

  .training-side {
    position: static;
  }

  .file-row,
  .corners-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
