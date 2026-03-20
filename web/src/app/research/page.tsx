'use client'

import { Calendar, MessageSquare, FileText, Lightbulb, FolderOpen } from 'lucide-react'
import Link from 'next/link'
import { useState, useEffect } from 'react'

import { Badge } from '~/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
import { ScrollArea } from '~/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '~/components/ui/tabs'

interface ResearchProject {
  id: number
  title: string
  description: string | null
  status: string
  tags: string | null
  created_at: string
  updated_at: string
}

interface ResearchSession {
  id: number
  project_id: number
  session_id: string
  title: string | null
  status: string
  created_at: string
  updated_at: string
  message_count: number
}

interface ResearchFinding {
  id: number
  project_id: number
  title: string
  content: string
  category: string
  confidence: number
  source_documents: string | null
  tags: string | null
  created_at: string
  updated_at: string
}

export default function ResearchPage() {
  const [projects, setProjects] = useState<ResearchProject[]>([])
  const [selectedProject, setSelectedProject] = useState<ResearchProject | null>(null)
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [findings, setFindings] = useState<ResearchFinding[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void fetchProjects()
  }, [])

  const fetchProjects = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api'
      const response = await fetch(`${apiUrl}/research/projects`)
      if (response.ok) {
        const data = await response.json()
        setProjects(data)
      } else {
        console.error('Failed to fetch projects:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchProjectDetails = async (projectId: number) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api'

      // Fetch sessions
      const sessionsResponse = await fetch(`${apiUrl}/research/projects/${projectId}/sessions`)
      if (sessionsResponse.ok) {
        const sessionsData = await sessionsResponse.json()
        setSessions(sessionsData)
      } else {
        console.error('Failed to fetch sessions:', sessionsResponse.statusText)
      }

      // Fetch findings
      const findingsResponse = await fetch(`${apiUrl}/research/projects/${projectId}/findings`)
      if (findingsResponse.ok) {
        const findingsData = await findingsResponse.json()
        setFindings(findingsData)
      } else {
        console.error('Failed to fetch findings:', findingsResponse.statusText)
      }
    } catch (error) {
      console.error('Failed to fetch project details:', error)
    }
  }

  const handleProjectSelect = (project: ResearchProject) => {
    setSelectedProject(project)
    void fetchProjectDetails(project.id)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading research history...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Back to Home
          </Link>
        </div>
        <h1 className="text-3xl font-bold mb-2">Research History</h1>
        <p className="text-muted-foreground">
          View your past research projects, conversations, and findings
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projects List */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FolderOpen className="h-5 w-5" />
                Research Projects
              </CardTitle>
              <CardDescription>
                {projects.length} project{projects.length !== 1 ? 's' : ''}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px]">
                <div className="space-y-3">
                  {projects.map((project) => (
                    <Card
                      key={project.id}
                      className={`cursor-pointer transition-all hover:bg-muted/50 ${
                        selectedProject?.id === project.id
                          ? 'border-primary border-2 shadow-md'
                          : 'border-border/20 border'
                      }`}
                      onClick={() => handleProjectSelect(project)}
                    >
                      <CardContent className="p-4">
                        <div className="space-y-2">
                          <h3 className="font-medium text-sm line-clamp-2">
                            {project.title}
                          </h3>
                          {project.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {project.description}
                            </p>
                          )}
                          <div className="flex items-center justify-between">
                            <Badge variant="secondary" className="text-xs">
                              {project.status}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(project.created_at)}
                            </span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  {projects.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground">
                      <FolderOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>No research projects yet</p>
                      <p className="text-sm">Start a research conversation to create your first project</p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Project Details */}
        <div className="lg:col-span-2">
          {selectedProject ? (
            <Tabs defaultValue="sessions" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="sessions" className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  Sessions ({sessions.length})
                </TabsTrigger>
                <TabsTrigger value="findings" className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4" />
                  Findings ({findings.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="sessions" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Chat Sessions</CardTitle>
                    <CardDescription>
                      Conversation history for {selectedProject.title}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[500px]">
                      <div className="space-y-3">
                        {sessions.map((session) => (
                          <Card key={session.id} className="cursor-pointer hover:bg-muted/50">
                            <CardContent className="p-4">
                              <div className="flex items-start justify-between">
                                <div className="space-y-1">
                                  <h4 className="font-medium text-sm">
                                    {session.title ?? `Session ${session.id}`}
                                  </h4>
                                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                      <MessageSquare className="h-3 w-3" />
                                      {session.message_count} messages
                                    </span>
                                    <span className="flex items-center gap-1">
                                      <Calendar className="h-3 w-3" />
                                      {formatDate(session.created_at)}
                                    </span>
                                  </div>
                                </div>
                                <Badge variant="outline" className="text-xs">
                                  {session.status}
                                </Badge>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                        {sessions.length === 0 && (
                          <div className="text-center py-8 text-muted-foreground">
                            <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No chat sessions yet</p>
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="findings" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Research Findings</CardTitle>
                    <CardDescription>
                      Key insights extracted from {selectedProject.title}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[500px]">
                      <div className="space-y-3">
                        {findings.map((finding) => (
                          <Card key={finding.id}>
                            <CardContent className="p-4">
                              <div className="space-y-3">
                                <div className="flex items-start justify-between">
                                  <h4 className="font-medium text-sm">{finding.title}</h4>
                                  <div className="flex items-center gap-2">
                                    <Badge variant="secondary" className="text-xs">
                                      {finding.category}
                                    </Badge>
                                    <span className="text-xs text-muted-foreground">
                                      {Math.round(finding.confidence * 100)}%
                                    </span>
                                  </div>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                  {finding.content}
                                </p>
                                <div className="flex items-center justify-between text-xs text-muted-foreground">
                                  <span>{formatDate(finding.created_at)}</span>
                                  {finding.tags && (
                                    <Badge variant="outline" className="text-xs">
                                      {finding.tags}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                        {findings.length === 0 && (
                          <div className="text-center py-8 text-muted-foreground">
                            <Lightbulb className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No research findings yet</p>
                            <p className="text-sm">Findings will be automatically extracted from AI responses</p>
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center h-[600px]">
                <div className="text-center text-muted-foreground">
                  <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
                  <h3 className="text-lg font-medium mb-2">Select a Research Project</h3>
                  <p>Choose a project from the list to view its details, sessions, and findings</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
