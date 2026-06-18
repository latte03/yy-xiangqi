import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';

export const useTrainingSampleStore = defineStore('trainingSample', () => {
  const file = shallowRef<File | null>(null);
  const corners = ref('');

  function setFile(nextFile: File | null) {
    file.value = nextFile;
    corners.value = '';
  }

  function setCorners(nextCorners: string) {
    corners.value = nextCorners;
  }

  function clear() {
    file.value = null;
    corners.value = '';
  }

  return {
    file,
    corners,
    setFile,
    setCorners,
    clear,
  };
});
