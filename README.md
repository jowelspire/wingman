# wingman
import React, { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

const samplePitches = [
  {
    id: 1,
    friendName: "Lina",
    singleName: "Jayden",
    reason: "Jayden is the funniest, most loyal person you'll meet. He once biked 12 miles to bring me soup when I was sick.",
    image: "https://randomuser.me/api/portraits/men/32.jpg",
  },
  {
    id: 2,
    friendName: "Mike",
    singleName: "Alana",
    reason: "Alana is sunshine in human form. She's a chef and a poet — literally.",
    image: "https://randomuser.me/api/portraits/women/65.jpg",
  }
];

export default function WingrApp() {
  const [pitches, setPitches] = useState(samplePitches);
  const [form, setForm] = useState({ friendName: '', singleName: '', reason: '', image: '' });

  const handleSubmit = () => {
    setPitches([{ id: Date.now(), ...form }, ...pitches]);
    setForm({ friendName: '', singleName: '', reason: '', image: '' });
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <h1 className="text-4xl font-bold text-center">Wingr: Pitch Your Single Friends</h1>

      <div className="space-y-4 border p-4 rounded-2xl shadow">
        <h2 className="text-2xl font-semibold">Create a Pitch</h2>
        <Input
          placeholder="Your name (wingman)"
          value={form.friendName}
          onChange={(e) => setForm({ ...form, friendName: e.target.value })}
        />
        <Input
          placeholder="Single friend's name"
          value={form.singleName}
          onChange={(e) => setForm({ ...form, singleName: e.target.value })}
        />
        <Input
          placeholder="Image URL"
          value={form.image}
          onChange={(e) => setForm({ ...form, image: e.target.value })}
        />
        <Textarea
          placeholder="Why should someone date them?"
          value={form.reason}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
        />
        <Button onClick={handleSubmit}>Post Pitch</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {pitches.map((pitch) => (
          <Card key={pitch.id} className="rounded-2xl shadow-xl">
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-4">
                <Avatar>
                  <AvatarImage src={pitch.image} />
                  <AvatarFallback>{pitch.singleName[0]}</AvatarFallback>
                </Avatar>
                <div>
                  <h3 className="text-xl font-semibold">{pitch.singleName}</h3>
                  <p className="text-sm text-gray-500">Pitched by {pitch.friendName}</p>
                </div>
              </div>
              <p className="text-base">{pitch.reason}</p>
              <Button variant="secondary">Request Intro</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
