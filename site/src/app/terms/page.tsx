import Navbar from '@/components/Navbar';
import Footer from '@/components/sections/Footer';

export const metadata = {
    title: 'Terms of Service — NeuralMind',
    description: 'Terms of service for NeuralMind. MIT-licensed OSS with a commercial license for teams.',
};

const sections = [
    {
        title: 'Introduction',
        body: 'By using NeuralMind, you agree to these terms. The Open Source Edition is MIT-licensed and subject to the MIT license terms below. The Pro and Commercial editions are covered by a separate Commercial License Agreement executed between you and Cheval-Volant LLC.',
    },
    {
        title: 'Open Source Edition (MIT)',
        body: 'The Open Source Edition of NeuralMind is licensed under the MIT License. You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to including the original copyright notice and disclaimer.',
        emphasize: 'For the full MIT license text, see the LICENSE file in the GitHub repository.',
    },
    {
        title: 'Key Permissions (MIT)',
        body: '',
        list: [
            'Commercial use: build and sell products that use NeuralMind',
            'Private use: use freely in internal projects without disclosure',
            'Modification: fork and adapt to your needs',
            'Distribution: redistribute the OSS version under the same license',
            'No warranty: MIT comes with no warranty — use at your own risk',
        ],
    },
    {
        title: 'Commercial Services',
        body: 'The core engine is MIT-licensed and free — all token savings included. The Team module (neuralmind/tier2) is source-available under the NeuralMind Commercial Modules License: free 1-seat use is included, and team or production use requires an executed agreement with Cheval-Volant LLC. Commercial services — AI-spend assessments, deployment and integration support, and related consulting — are provided under a separate agreement.',
        emphasize: 'Contact hello@neuralmind.uk for service terms.',
    },
    {
        title: 'Acceptable Use',
        body: 'You agree not to:',
        list: [
            'Remove or obscure the MIT license notice in distributions',
            'Sell the OSS version without modification under the NeuralMind trademark',
            'Use NeuralMind to exfiltrate code from environments without authorization — its local-only design is a guarantee to you, not a license to bypass security controls on others\' codebases',
            'Use the consulting or CFO advisory offerings to misrepresent financial or technical outcomes',
        ],
    },
    {
        title: 'Disclaimer of Warranty',
        body: 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY.',
    },
    {
        title: 'Limitation of Liability',
        body: 'IN NO EVENT SHALL CHEVAL-VOLANT LLC BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE OR SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.',
    },
    {
        title: 'Changes to Terms',
        body: 'Material changes to these terms will be communicated via the GitHub issue tracker and email to registered license holders at least 30 days before taking effect. The OSS version\'s MIT license is irrevocable for existing copies but may be updated for new releases.',
    },
    {
        title: 'Contact',
        body: 'Legal inquiries: hello@neuralmind.uk',
    },
];

export default function Terms() {
    return (
        <>
            <Navbar />
            <main className="pt-32 pb-20 px-4 md:px-6">
                <article className="max-w-3xl mx-auto">
                    <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">Terms of Service</h1>
                    <p className="text-slate-400 text-lg mb-12">Last updated: July 2026</p>
                    {sections.map((s) => (
                        <div key={s.title} className="mb-10">
                            <h2 className="font-display text-2xl font-bold text-white mb-3 border-l-4 border-proton pl-4">{s.title}</h2>
                            {s.body && <p className="text-slate-300 leading-relaxed">{s.body}</p>}
                            {s.list && (
                                <ul className="mt-3 space-y-2 text-slate-300">
                                    {s.list.map((item) => (
                                        <li key={item} className="flex items-start gap-2">
                                            <span className="text-proton mt-1.5">•</span>
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {s.emphasize && (
                                <p className="text-electric text-sm mt-2 font-semibold">{s.emphasize}</p>
                            )}
                        </div>
                    ))}
                </article>
            </main>
            <Footer />
        </>
    );
}
