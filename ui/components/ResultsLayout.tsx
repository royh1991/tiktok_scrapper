import { cn } from '@/lib/utils';
export const ResultsLayout = ({ children, className }: { children: React.ReactNode; className?: string }) => {
    return (
        <div className={cn("container mx-auto px-4 py-8", className)}>
            {children}
        </div>
    )
}
