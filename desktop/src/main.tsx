import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, type Project, type Task } from './api';
import './styles.css';

function App() {
  const [health, setHealth] = useState('checking');
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [message, setMessage] = useState('');
  const [objective, setObjective] = useState('');

  async function refresh(projectId?: string) {
    try {
      await api.health();
      setHealth('online');
      const projectResult = await api.projects();
      setProjects(projectResult.items);
      const active = projectId ? projectResult.items.find((item) => item.id === projectId) : selected || projectResult.items[0];
      setSelected(active || null);
      setTasks(active ? (await api.tasks(active.id)).items : []);
    } catch (error) {
      setHealth('offline');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function addProject() {
    const name = window.prompt('Project name');
    if (!name?.trim()) return;
    const result = await api.createProject(name.trim());
    await refresh(result.project.id);
  }

  async function addTask(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || !objective.trim()) return;
    await api.createTask(selected.id, objective.trim());
    setObjective('');
    await refresh(selected.id);
  }

  return <div className="app-shell">
    <header><div><p className="eyebrow">CATALOG GOVERNANCE</p><h1>Cross-border Cowork</h1></div><span className={`health ${health}`}>API {health}</span></header>
    <main>
      <aside><div className="section-heading"><h2>Projects</h2><button onClick={() => void addProject()}>+</button></div>{projects.map((project) => <button className={`project ${selected?.id === project.id ? 'selected' : ''}`} key={project.id} onClick={() => void refresh(project.id)}>{project.name}</button>)}{!projects.length && <p className="muted">Create a project to begin.</p>}</aside>
      <section className="workspace"><div className="section-heading"><div><p className="eyebrow">WORKSPACE</p><h2>{selected?.name || 'Choose a project'}</h2></div><button onClick={() => void refresh(selected?.id)}>Refresh</button></div>{selected && <form className="task-form" onSubmit={(event) => void addTask(event)}><input value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="Describe a catalog task" /><button type="submit">Create task</button></form>}<div className="task-list">{tasks.map((task) => <article className="task-card" key={task.id}><div><strong>{task.objective}</strong><p className="muted">{task.id}</p></div><span className={`status ${task.status}`}>{task.status}</span></article>)}{selected && !tasks.length && <p className="muted">No tasks yet.</p>}{message && <p className="error">{message}</p>}</div></section>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
