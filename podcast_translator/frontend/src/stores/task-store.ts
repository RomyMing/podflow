import { create } from 'zustand'

import { enableSampleTasks, isDemoExperience } from '@/config/app-config'
import { SAMPLE_TASK, isSampleTaskId } from '@/lib/demo-sample-task'
import { formatTaskErrorMessage } from '@/lib/task-display'
import { getTaskTitle } from '@/lib/task-title'
import { TaskWebSocket } from '@/lib/websocket'
import { TaskService } from '@/services/task-service'
import { useToastStore } from '@/stores/toast-store'
import { TaskResponse, TaskStatus, WSProgressMessage } from '@/types/api'

interface FetchTaskOptions {
  silent?: boolean
}

interface FetchTasksOptions {
  silent?: boolean
}

interface TaskState {
  tasks: TaskResponse[]
  currentTask: TaskResponse | null
  isLoading: boolean
  error: string | null
  wsConnections: Record<string, TaskWebSocket>
  notifiedTerminalStatuses: Record<string, TaskStatus>
  fetchTasks: (skip?: number, limit?: number, options?: FetchTasksOptions) => Promise<void>
  fetchTaskById: (id: string, options?: FetchTaskOptions) => Promise<void>
  subscribeToProgress: (taskId: string) => void
  unsubscribeFromProgress: (taskId: string) => void
  updateTaskProgress: (msg: WSProgressMessage) => void
}

function shouldIgnoreStatusRegression(prevTask: TaskResponse | null, nextStatus: TaskStatus): boolean {
  return !!prevTask && isTerminalStatus(prevTask.status) && prevTask.status !== nextStatus
}

function resolveTaskSnapshot(nextTask: TaskResponse): TaskResponse {
  // REST responses are authoritative snapshots. A failed task can legitimately
  // return to processing after a manual/automatic resume, so terminal-state
  // protection must only apply to asynchronous websocket messages that may be
  // stale or arrive out of order.
  return nextTask
}

function findTaskSnapshot(
  tasks: TaskResponse[],
  currentTask: TaskResponse | null,
  taskId: string,
): TaskResponse | null {
  return (currentTask?.id === taskId ? currentTask : null)
    ?? tasks.find((task) => task.id === taskId)
    ?? null
}

function mergeTaskProgress(task: TaskResponse, msg: WSProgressMessage): TaskResponse {
  if (shouldIgnoreStatusRegression(task, msg.status)) {
    return task
  }

  return {
    ...task,
    status: msg.status,
    current_stage: msg.stage ?? task.current_stage,
    progress_percent: msg.progress_percent,
    stage_progress_percent: msg.stage_progress_percent ?? task.stage_progress_percent,
    error_message: msg.error_message ?? task.error_message,
    pause_reason_code: msg.pause_reason_code ?? task.pause_reason_code,
    provider_error_code: msg.provider_error_code ?? task.provider_error_code,
    output_audio_url: msg.output_audio_url ?? task.output_audio_url,
    audio_duration: msg.audio_duration ?? task.audio_duration,
    eta_seconds: msg.eta_seconds ?? task.eta_seconds,
    finished_at: msg.finished_at ?? task.finished_at,
  }
}

function isTerminalStatus(status: TaskStatus): boolean {
  return status === 'completed' || status === 'failed'
}

function buildTerminalToastMessage(task: TaskResponse): { type: 'success' | 'error'; message: string } | null {
  const taskTitle = getTaskTitle(task)

  if (task.status === 'completed') {
    return {
      type: 'success',
      message: `${taskTitle} 已完成，可以播放或下载结果。`,
    }
  }

  if (task.status === 'failed') {
    const displayError = formatTaskErrorMessage(task.error_message)

    return {
      type: 'error',
      message: displayError
        ? `${taskTitle} 失败：${displayError}`
        : `${taskTitle} 处理失败，请打开详情页查看原因。`,
    }
  }

  return null
}

function notifyTerminalTransition(
  prevTask: TaskResponse | null,
  nextTask: TaskResponse,
  notifiedTerminalStatuses: Record<string, TaskStatus>,
): Record<string, TaskStatus> {
  if (!isTerminalStatus(nextTask.status)) {
    return notifiedTerminalStatuses
  }

  const didJustEnterTerminal = prevTask !== null && prevTask.status !== nextTask.status
  const alreadyNotifiedForThisStatus = notifiedTerminalStatuses[nextTask.id] === nextTask.status

  if (!didJustEnterTerminal || alreadyNotifiedForThisStatus) {
    return notifiedTerminalStatuses
  }

  const payload = buildTerminalToastMessage(nextTask)
  if (payload) {
    useToastStore.getState().showToast(payload.message, payload.type, payload.type === 'error' ? 7000 : 5000)
  }

  return {
    ...notifiedTerminalStatuses,
    [nextTask.id]: nextTask.status,
  }
}

function upsertTask(tasks: TaskResponse[], task: TaskResponse): TaskResponse[] {
  const existingIndex = tasks.findIndex((item) => item.id === task.id)
  if (existingIndex === -1) {
    return [task, ...tasks]
  }

  return tasks.map((item) => (item.id === task.id ? task : item))
}

function shouldInjectSampleTask(): boolean {
  return isDemoExperience || enableSampleTasks
}

function withSampleTask(tasks: TaskResponse[]): TaskResponse[] {
  if (!shouldInjectSampleTask()) {
    return tasks
  }

  if (tasks.some((task) => task.id === SAMPLE_TASK.id)) {
    return tasks
  }

  return [SAMPLE_TASK, ...tasks]
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  currentTask: null,
  isLoading: false,
  error: null,
  wsConnections: {},
  notifiedTerminalStatuses: {},

  fetchTasks: async (skip = 0, limit = 20, options: FetchTasksOptions = {}) => {
    if (!options.silent) {
      set({ isLoading: true, error: null })
    }

    try {
      const fetchedTasks = withSampleTask(await TaskService.listTasks(skip, limit))

      set((state) => {
        const tasks = fetchedTasks.map((task) => (
          resolveTaskSnapshot(task)
        ))

        return {
          tasks,
          currentTask: state.currentTask,
          notifiedTerminalStatuses: state.notifiedTerminalStatuses,
          isLoading: options.silent ? state.isLoading : false,
          error: null,
        }
      })
    } catch (err: unknown) {
      const error = err as Error
      set((state) => ({
        error: formatTaskErrorMessage(error.message) || '任务列表加载失败',
        isLoading: options.silent ? state.isLoading : false,
      }))
    } finally {
      if (!options.silent) {
        set({ isLoading: false })
      }
    }
  },

  fetchTaskById: async (id: string, options: FetchTaskOptions = {}) => {
    if (!options.silent) {
      set({ isLoading: true, error: null })
    }

    try {
      if (isSampleTaskId(id) && shouldInjectSampleTask()) {
        set((state) => ({
          currentTask: SAMPLE_TASK,
          tasks: upsertTask(state.tasks, SAMPLE_TASK),
          isLoading: options.silent ? state.isLoading : false,
          error: null,
        }))
        return
      }

      const task = await TaskService.getTask(id)
      set((state) => {
        const previousTask = findTaskSnapshot(state.tasks, state.currentTask, task.id)
        const nextTask = resolveTaskSnapshot(task)

        return {
          currentTask: nextTask,
          tasks: upsertTask(withSampleTask(state.tasks), nextTask),
          notifiedTerminalStatuses: notifyTerminalTransition(
            previousTask,
            nextTask,
            state.notifiedTerminalStatuses,
          ),
          isLoading: options.silent ? state.isLoading : false,
          error: null,
        }
      })
    } catch (err: unknown) {
      const error = err as Error
      if (isSampleTaskId(id) && shouldInjectSampleTask()) {
        set((state) => ({
          currentTask: SAMPLE_TASK,
          tasks: upsertTask(state.tasks, SAMPLE_TASK),
          isLoading: options.silent ? state.isLoading : false,
          error: null,
        }))
      } else {
        set((state) => ({
          error: formatTaskErrorMessage(error.message) || '任务详情加载失败',
          isLoading: options.silent ? state.isLoading : false,
        }))
      }
    } finally {
      if (!options.silent) {
        set({ isLoading: false })
      }
    }
  },

  subscribeToProgress: (taskId: string) => {
    const { wsConnections, updateTaskProgress } = get()
    if (wsConnections[taskId]) {
      return
    }

    const ws = new TaskWebSocket(taskId)
    ws.connect((msg) => {
      updateTaskProgress(msg)
    })

    set({
      wsConnections: {
        ...wsConnections,
        [taskId]: ws,
      },
    })
  },

  unsubscribeFromProgress: (taskId: string) => {
    const { wsConnections } = get()
    const ws = wsConnections[taskId]
    if (!ws) {
      return
    }

    ws.disconnect()
    const nextConnections = { ...wsConnections }
    delete nextConnections[taskId]
    set({ wsConnections: nextConnections })
  },

  updateTaskProgress: (msg: WSProgressMessage) => {
    set((state) => {
      const previousTask = findTaskSnapshot(state.tasks, state.currentTask, msg.task_id)

      if (shouldIgnoreStatusRegression(previousTask, msg.status)) {
        return state
      }

      const nextTaskFromMessage = previousTask
        ? mergeTaskProgress(previousTask, msg)
        : null

      const updatedTasks = nextTaskFromMessage
        ? upsertTask(state.tasks, nextTaskFromMessage)
        : state.tasks

      const updatedCurrentTask =
        state.currentTask && state.currentTask.id === msg.task_id
          ? nextTaskFromMessage ?? mergeTaskProgress(state.currentTask, msg)
          : state.currentTask

      return {
        tasks: updatedTasks,
        currentTask: updatedCurrentTask,
        notifiedTerminalStatuses: nextTaskFromMessage
          ? notifyTerminalTransition(previousTask, nextTaskFromMessage, state.notifiedTerminalStatuses)
          : state.notifiedTerminalStatuses,
      }
    })
  },
}))
