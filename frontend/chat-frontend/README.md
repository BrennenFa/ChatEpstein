# Epstein Document Research - Frontend

A professional, authoritative legal document analysis interface built with Next.js 15, TypeScript, and Tailwind CSS.

## Design Principles

- **Professionalism**: Clean, minimal, trustworthy design
- **Security**: Looks secure and official
- **Accessibility**: WCAG compliant, keyboard navigation, high contrast
- **Authority**: Designed to feel like a trusted digital law clerk, not a casual chatbot

## Features

- Real-time chat interface for document queries
- Professional citation display with document IDs and page numbers
- Responsive design for desktop and mobile
- Loading states and error handling
- Clean, readable typography optimized for legal text

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Font**: Geist Sans (professional, readable)

## Getting Started

### Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000)

### Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
frontend/chat-frontend/
├── app/
│   ├── api/chat/         # API routes (Next.js backend)
│   ├── layout.tsx        # Root layout with metadata
│   ├── page.tsx          # Main page
│   └── globals.css       # Global styles
├── components/
│   ├── ChatInterface.tsx # Main chat container
│   ├── Header.tsx        # Top navigation bar
│   ├── MessageList.tsx   # Message container
│   ├── MessageBubble.tsx # Individual message display
│   ├── CitationCard.tsx  # Source citation display
│   ├── InputArea.tsx     # Message input field
│   └── LoadingIndicator.tsx # Loading animation
└── types/
    └── chat.ts           # TypeScript interfaces
```

## Connecting to Backend

The frontend expects your FastAPI backend to provide an endpoint:

**Endpoint**: `POST /api/query`

**Request**:
```json
{
  "question": "Who are the key individuals mentioned?"
}
```

**Response**:
```json
{
  "answer": "**Findings:**\\n[Your analysis]\\n\\n**Source Evidence:**\\n1. **Document [ID], Page [#]:** \\"Quote\\"",
  "sources": [
    {
      "documentId": "EFTA00016128",
      "pageNumber": "5",
      "quote": "Exact quote from document"
    }
  ]
}
```

### Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Then update `app/api/chat/route.ts` to uncomment the backend call.

## Deployment to Vercel

### Option 1: Vercel Dashboard

1. Push code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Import repository
4. Set **Root Directory** to `frontend/chat-frontend`
5. Add environment variable: `NEXT_PUBLIC_BACKEND_URL`
6. Deploy

### Option 2: Vercel CLI

```bash
cd frontend/chat-frontend
vercel
```

## Customization

### Colors

The theme uses professional slate colors. To change:

- Edit Tailwind classes in components
- Modify `globals.css` for custom properties

### Fonts

Currently using Geist Sans. To change:

- Edit `app/layout.tsx`
- Update font imports

### Branding

- Update `app/layout.tsx` metadata
- Modify `components/Header.tsx` for logo/title

## Accessibility

- ✅ Keyboard navigation
- ✅ ARIA labels
- ✅ High contrast ratios
- ✅ Focus indicators
- ✅ Screen reader friendly

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

Private research tool
