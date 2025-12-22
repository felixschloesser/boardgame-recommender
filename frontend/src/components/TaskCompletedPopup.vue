<script lang="ts" setup>
interface Props {
  visible: boolean
}

const props = defineProps<Props>()

const emit = defineEmits(['close'])

const openQuestionnaire = () => {
  const participant_id = localStorage.getItem('participant_id')
  const session_type = localStorage.getItem('session_type')
  const link_to_questionnaire = `https://forms.office.com/Pages/ResponsePage.aspx?id=m1hzOUCetU6ADrC2OD0WIWDTpTeScE9JrBYStf8YoldUQ01BRjBMWUpKRVVTTTdFT1dLVTc5MFo0WS4u&r012cbe1c0c8e4f43a3d2ba264e1062c4=${participant_id}&r3529d9540eb242369503b3859521d1d6="Session%20type%20${session_type}"`
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
