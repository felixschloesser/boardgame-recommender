<script lang="ts" setup>
const participant_id = localStorage.getItem('participant_id')
const link_to_questionnaire = `https://example.com/questionnaire?participant_id=${participant_id}`

interface Props {
  visible: boolean
}

const props = defineProps<Props>()

const emit = defineEmits(['close'])

const openQuestionnaire = () => {
  window.open(link_to_questionnaire, '_blank')
}
</script>

<template>
  <div v-if="props.visible" class="popup-backdrop">
    <div class="popup-content">
      <h2 class="popup-header">You completed the task!</h2>
      <p>You can continue to explore the app after you submit your feedback</p>
      <p>Please fill in the questionnaire below to finish our study.</p>
      <div class="button-group">
        <button class="btn-primary" @click="openQuestionnaire">Open Questionnaire</button>
        <button class="btn-primary not-ready" @click="emit('close')">I am not ready yet</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.button-group {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
  gap: var(--space-3);
}

.not-ready {
  background: #bfdbfe; /* blue-200 */
  color: #64748b; /* slate-500 */
}

.popup-header {
  font-size: var(--text-xl);
  color: var(--color-success);
  margin-bottom: var(--space-4);
}

.popup-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.popup-content {
  background: var(--color-bg);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  text-align: center;
  max-width: 400px;
  width: 100%;
}
</style>
